"""Plugin-bundled connection helper. No Tara wheel or mandatory Tara reader.

Keep this source beside your notebook or add the plugin's client directory to
PYTHONPATH. Native adapters import only the library selected by the caller.
"""

from __future__ import annotations

import asyncio
import os
import threading
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse


class DataAccessError(RuntimeError):
    """Fixed, non-secret errors: native capability URLs must not be printed."""


class _ArrowRows:
    def __init__(self, source):
        self.source = source
        self._pid = os.getpid()

    def __call__(self):
        if os.getpid() != self._pid:
            raise DataAccessError(
                "Arrow HF bridges use num_workers=0; use Parquet for worker sharding."
            )
        for batch in self.source.arrow_batches():
            yield from batch.to_pylist()

    def __getstate__(self):
        # HF fingerprints generators with dill. Identity never includes tokens,
        # capability URLs or a live event loop. This bridge is one local reader.
        return {k: self.source.metadata[k] for k in ("product", "revision", "options")}

    def __setstate__(self, state):
        raise DataAccessError(
            "Arrow HF bridges use num_workers=0; use Parquet for worker sharding."
        )


def _mds_downloader(scheme):
    from streaming.base.storage.download import CloudDownloader

    class TaraDownloader(CloudDownloader):
        @staticmethod
        def _client_identifier():
            return scheme

        def __reduce__(self):
            return _mds_downloader, (scheme,)

        def clean_up(self):
            pass

        def _download_file_impl(self, remote, local, timeout):
            import requests

            origin = remote.replace("tara+", "", 1)
            parsed = urlparse(origin)
            if (
                not parsed.path.startswith("/data/files/")
                or parsed.query
                or parsed.fragment
                or parsed.username
            ):
                raise DataAccessError("MDS download source is invalid.")
            if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
                raise DataAccessError("MDS download requires HTTPS.")
            destination = Path(local)
            temporary = destination.with_name(destination.name + ".tmp")
            try:
                with requests.get(
                    origin, stream=True, timeout=min(timeout, 60), allow_redirects=False
                ) as response:
                    if response.status_code != 200:
                        raise DataAccessError("MDS download refused; check lease and quota.")
                    length = int(response.headers.get("Content-Length", "0"))
                    if not 0 < length <= 64 * 1024**2:
                        raise DataAccessError("MDS shard exceeds its byte bound.")
                    total = 0
                    with temporary.open("wb") as handle:
                        for chunk in response.iter_content(65536):
                            total += len(chunk)
                            if total > length:
                                raise DataAccessError("MDS source changed during transfer.")
                            handle.write(chunk)
                    if total != length:
                        raise DataAccessError("MDS download was incomplete.")
                temporary.replace(destination)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise DataAccessError(
                    "MDS download failed; check access, source and quota."
                ) from None

    return TaraDownloader()


def _install_mds_http():
    # Mosaic 0.13 has no HTTP downloader. Register dedicated schemes, leaving
    # stock storage handlers untouched and keeping native resume/sharding.
    from streaming.base.storage.download import DOWNLOADER_MAPPINGS

    for scheme in ("tara+https", "tara+http"):
        DOWNLOADER_MAPPINGS.setdefault(scheme, lambda s=scheme: _mds_downloader(s))


class TaraSource:
    def __init__(self, connection, metadata):
        self.connection, self.metadata = connection, metadata
        self._manifest = None
        self._cursor = None
        self._done = False
        self._closed = False
        self._error = None
        self._renewal = connection._run(self._start_renewal())

    async def _start_renewal(self):
        return asyncio.create_task(self._keep_alive())

    async def _keep_alive(self):
        while not self._closed:
            await asyncio.sleep(max(1, (self.metadata["expires_at"] - time.time()) / 2))
            try:
                self.metadata = await self.connection._request(
                    "POST", "/data/renew", {"access_handle": self.metadata["access_handle"]}
                )
            except Exception:
                self._error = DataAccessError(
                    "Dataset access renewal failed; reconnect before continuing."
                )
                return

    def _check(self):
        if self._closed:
            raise DataAccessError("Dataset access is closed.")
        if self._error:
            raise self._error from None

    def manifest(self):
        self._check()
        if self._manifest is None:
            self._manifest = self.connection._run(
                self.connection._request(
                    "POST", "/data/manifest", {"access_handle": self.metadata["access_handle"]}
                )
            )
        return self._manifest

    def parquet_files(self, *, rank=0, world_size=1, names=None):
        """Deterministic file sharding, pinned order. Returned URLs are private."""
        self._check()
        if (
            self.metadata["format"] != "parquet"
            or type(rank) is not int
            or type(world_size) is not int
            or not 0 <= rank < world_size
        ):
            raise DataAccessError("Choose a Parquet product and a valid shard.")
        files = self.manifest()["files"]
        if names is not None:
            wanted = set(names)
            if wanted - {f["name"] for f in files}:
                raise DataAccessError("A selected file is outside this product.")
            files = [f for f in files if f["name"] in wanted]
        return [f["url"] for i, f in enumerate(files) if i % world_size == rank]

    def hf(self, *, rank=0, world_size=1, names=None, columns=None, filters=None):
        from datasets import IterableDataset

        if self.metadata["format"] == "parquet":
            paths = self.parquet_files(rank=rank, world_size=world_size, names=names)
            if not paths:
                return IterableDataset.from_generator(lambda: iter(()))
            import pyarrow.dataset as pa_dataset
            from datasets.data_files import DataFilesDict, DataFilesList

            # HF's generic HTTP glob performs a full GET to test existence. The
            # registry already resolved files, so use its typed inventory and
            # the native Parquet reader; large files remain strictly ranged.
            files = DataFilesDict(
                {
                    "train": DataFilesList(
                        paths, origin_metadata=[(self.metadata["revision"],)] * len(paths)
                    )
                }
            )
            return IterableDataset.from_parquet(
                files,
                split="train",
                columns=columns,
                filters=filters,
                batch_size=self.metadata["options"]["batch_rows"],
                fragment_scan_options=pa_dataset.ParquetFragmentScanOptions(pre_buffer=False),
            )
        if self.metadata["format"] != "arrow" or rank != 0 or world_size != 1:
            raise DataAccessError(
                "Arrow conditions use a single keyset reader; prepare distinct conditions for workers."
            )

        return IterableDataset.from_generator(_ArrowRows(self))

    def polars(self, *, names=None, rank=0, world_size=1):
        import polars as pl

        if self.metadata["format"] != "parquet":
            raise DataAccessError("Use polars_batches for a condition Arrow product.")
        return pl.scan_parquet(self.parquet_files(names=names, rank=rank, world_size=world_size))

    def arrow_batches(self, *, cursor=None):
        import pyarrow as pa

        self._check()
        if self.metadata["format"] != "arrow":
            raise DataAccessError("Choose an Arrow condition product.")
        current = cursor
        while True:
            self._check()
            raw, next_cursor = self.connection._run(
                self.connection._batch(self.metadata["access_handle"], current)
            )
            reader = pa.ipc.open_stream(raw)
            batches = list(reader)
            if len(batches) != 1:
                raise DataAccessError("Expected one bounded Arrow batch per request.")
            self._cursor, self._done = next_cursor, not next_cursor
            # Persist this checkpoint only after processing the yielded batch.
            yield batches[0]
            if not next_cursor:
                return
            current = next_cursor

    @property
    def checkpoint(self):
        return {
            "product": self.metadata["product"],
            "revision": self.metadata["revision"],
            "options": self.metadata["options"],
            "cursor": self._cursor,
            "done": self._done,
        }

    def csr_batches(self, gene_tokens, *, cursor=None):
        """Sparse cells x genes; explicit pinned token axis, never a dense atlas.

        Returns (cell RecordBatch, scipy CSR). Removes only the paired HF CLS
        token 1 / expression -2. Unknown tokens fail instead of changing axes.
        """
        import numpy as np
        from scipy.sparse import csr_matrix

        if self.metadata["layer"] != "single_cell":
            raise DataAccessError("Choose a single-cell product for sparse CSR batches.")
        axis = {token: i for i, token in enumerate(gene_tokens)}
        if len(axis) != len(gene_tokens) or any(type(g) is not int or g <= 1 for g in axis):
            raise DataAccessError("Provide a unique pinned gene-token axis without CLS.")
        for batch in self.arrow_batches(cursor=cursor):
            indices, values, pointers = [], [], [0]
            for genes, counts in zip(
                batch["genes"].to_pylist(), batch["expressions"].to_pylist(), strict=True
            ):
                if not genes or genes[0] != 1 or counts[0] != -2 or len(genes) != len(counts):
                    raise DataAccessError("Sparse cell arrays do not match the declared schema.")
                for gene, count in zip(genes[1:], counts[1:], strict=True):
                    if gene not in axis or not np.isfinite(count) or count < 0:
                        raise DataAccessError("Sparse cells do not match the pinned gene axis.")
                    if count:
                        indices.append(axis[gene])
                        values.append(count)
                pointers.append(len(values))
            matrix = csr_matrix(
                (
                    np.asarray(values, dtype=np.float32),
                    np.asarray(indices, dtype=np.int64),
                    np.asarray(pointers, dtype=np.int64),
                ),
                shape=(batch.num_rows, len(axis)),
            )
            matrix.sort_indices()
            yield batch, matrix

    def polars_batches(self, *, cursor=None):
        import polars as pl

        for batch in self.arrow_batches(cursor=cursor):
            yield pl.from_arrow(batch)

    def mds(self, *, local, **kwargs):
        from streaming import StreamingDataset

        self._check()
        if (
            self.metadata["format"] != "mds"
            or "streams" in kwargs
            or "remote" in kwargs
            or "allow_unsafe_types" in kwargs
        ):
            raise DataAccessError(
                "Choose a safe MDS product; remote and unsafe encodings are managed by Tara."
            )
        _install_mds_http()
        kwargs.setdefault("predownload", 128)
        kwargs.setdefault("cache_limit", "256mb")
        kwargs.setdefault("download_retry", 1)
        return StreamingDataset(
            remote="tara+" + self.manifest()["remote"],
            local=str(local),
            allow_unsafe_types=False,
            **kwargs,
        )

    def close(self):
        if self._closed:
            return
        try:
            self.connection._run(
                self.connection._request(
                    "POST",
                    "/data/renew",
                    {"access_handle": self.metadata["access_handle"], "close": True},
                )
            )
        finally:
            self._closed = True
            self.connection._loop.call_soon_threadsafe(self._renewal.cancel)
            self.connection._sources.discard(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class TaraConnection:
    def __init__(self, base_url="https://tara.tahoebio.io", *, auth=None, transport=None):
        origin = urlparse(base_url)
        if origin.scheme != "https" and not (
            origin.scheme == "http" and origin.hostname in {"127.0.0.1", "localhost", "testserver"}
        ):
            raise DataAccessError("Use HTTPS for the public service.")
        if (
            origin.username
            or origin.password
            or origin.query
            or origin.fragment
            or origin.path not in {"", "/"}
        ):
            raise DataAccessError("Use a service origin without credentials or a path.")
        self.base_url, self._auth, self._transport = base_url.rstrip("/"), auth, transport
        self._sources = set()
        self._closed = False
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._run(self._open())

    async def _open(self):
        import httpx2

        if self._auth is None:
            from fastmcp.client.auth import OAuth

            self._auth = OAuth(self.base_url + "/mcp", client_name="Tara Data Reader")
        self._http = httpx2.AsyncClient(
            base_url=self.base_url,
            auth=self._auth,
            transport=self._transport,
            timeout=65,
            follow_redirects=False,
        )

    def _run(self, coroutine):
        future = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        try:
            return future.result(timeout=360)
        except DataAccessError:
            raise
        except Exception:
            future.cancel()
            raise DataAccessError(
                "Dataset request failed. Check sign-in, source options and quota."
            ) from None

    async def _request(self, method, path, value=None):
        response = await self._http.request(method, path, json=value)
        if response.status_code != 200:
            # Preserve the fixed error code/status only, never native URLs.
            reason = response.json().get("error", "request_failed")
            if reason not in {
                "sign_in_required",
                "not_invited",
                "rate_limited",
                "release_mismatch",
                "bad_request",
                "body_too_large",
                "dataset_not_allowed",
                "source_changed",
                "not_found",
                "service_paused",
                "service_unavailable",
            }:
                reason = "request_failed"
            raise DataAccessError(f"Dataset request refused ({response.status_code}: {reason}).")
        return response.json()

    async def _batch(self, handle, cursor):
        response = await self._http.post(
            "/data/batch", json={"access_handle": handle, "cursor": cursor}
        )
        if response.status_code != 200:
            raise DataAccessError(f"Dataset batch refused ({response.status_code}).")
        if len(response.content) > 8 * 1024**2:
            raise DataAccessError("Dataset batch exceeded the byte bound.")
        return response.content, response.headers.get("X-Tara-Cursor") or None

    def products(self):
        return self._run(self._request("GET", "/data/products"))["products"]

    def conditions(self, product, *, cell_line=None, offset=0):
        """Bounded pages of approved public filters, without a backend query."""
        values = {"product": product, "offset": offset}
        if cell_line is not None:
            values["cell_line"] = cell_line
        return self._run(self._request("GET", "/data/conditions?" + urlencode(values)))

    def prepare(self, product, *, revision=None, **options):
        metadata = self._run(
            self._request(
                "POST",
                "/data/prepare",
                {"product": product, "revision": revision, "options": options},
            )
        )
        source = TaraSource(self, metadata)
        self._sources.add(source)
        return source

    def open(self, access_handle):
        """Redeem prepare_dataset's account-bound handle using this runtime's OAuth."""
        metadata = self._run(
            self._request("POST", "/data/access", {"access_handle": access_handle})
        )
        source = TaraSource(self, metadata)
        self._sources.add(source)
        return source

    def close(self):
        if self._closed:
            return
        error = None
        try:
            for source in list(self._sources):
                try:
                    source.close()
                except DataAccessError as denied:
                    error = denied
        finally:
            try:
                self._run(self._http.aclose())
            finally:
                self._closed = True
                self._loop.call_soon_threadsafe(self._loop.stop)
                self._thread.join(timeout=5)
                self._loop.close()
        if error:
            raise error

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def connect(base_url="https://tara.tahoebio.io", **kwargs):
    """Use the existing public OAuth provider, with refresh, in this Python runtime.

    Hosts with a credential bridge may pass their HTTPX auth provider. Otherwise
    FastMCP opens the standard public browser sign-in once per connection. It does
    not extract another host's credentials or require a service account.
    """
    return TaraConnection(base_url, **kwargs)
