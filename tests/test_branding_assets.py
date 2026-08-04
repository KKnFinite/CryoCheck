"""Final logo, favicon, and application-icon coverage."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import zlib
from pathlib import Path


_IMAGE_DIRECTORY = Path("app/static/img")
_APPROVED_LOGOS = {
    "logo_blue.png": {
        "sha256": (
            "0841578a9e39a8b6248cb6d95a6cf1230d5f66be04b5244af12bfcc901f75581"
        ),
        "transparent_pixels": 764103,
    },
    "logo_silver.png": {
        "sha256": (
            "b856177e3840110d5a994dc2ba9c481deda58a09871f214511809be7013070ad"
        ),
        "transparent_pixels": 715125,
    },
}


def _paeth(left: int, above: int, upper_left: int) -> int:
    estimate = left + above - upper_left
    left_distance = abs(estimate - left)
    above_distance = abs(estimate - above)
    upper_left_distance = abs(estimate - upper_left)
    if left_distance <= above_distance and left_distance <= upper_left_distance:
        return left
    if above_distance <= upper_left_distance:
        return above
    return upper_left


def _rgba_png_details(payload: bytes) -> tuple[int, int, int]:
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"
    offset = 8
    compressed = bytearray()
    width = height = None
    bit_depth = color_type = interlace = None

    while offset < len(payload):
        length = struct.unpack(">I", payload[offset : offset + 4])[0]
        chunk_type = payload[offset + 4 : offset + 8]
        chunk_data = payload[offset + 8 : offset + 8 + length]
        offset += 12 + length
        if chunk_type == b"IHDR":
            (
                width,
                height,
                bit_depth,
                color_type,
                _compression,
                _filter,
                interlace,
            ) = struct.unpack(">IIBBBBB", chunk_data)
        elif chunk_type == b"IDAT":
            compressed.extend(chunk_data)
        elif chunk_type == b"IEND":
            break

    assert width is not None
    assert height is not None
    assert bit_depth == 8
    assert color_type == 6
    assert interlace == 0

    raw = zlib.decompress(compressed)
    stride = width * 4
    previous = bytearray(stride)
    raw_offset = 0
    transparent_pixels = 0

    for _row_index in range(height):
        filter_type = raw[raw_offset]
        raw_offset += 1
        filtered = raw[raw_offset : raw_offset + stride]
        raw_offset += stride
        reconstructed = bytearray(stride)

        for index, value in enumerate(filtered):
            left = reconstructed[index - 4] if index >= 4 else 0
            above = previous[index]
            upper_left = previous[index - 4] if index >= 4 else 0
            if filter_type == 0:
                reconstructed[index] = value
            elif filter_type == 1:
                reconstructed[index] = (value + left) & 0xFF
            elif filter_type == 2:
                reconstructed[index] = (value + above) & 0xFF
            elif filter_type == 3:
                reconstructed[index] = (
                    value + ((left + above) // 2)
                ) & 0xFF
            elif filter_type == 4:
                reconstructed[index] = (
                    value + _paeth(left, above, upper_left)
                ) & 0xFF
            else:
                raise AssertionError(f"Unsupported PNG filter {filter_type}")

        transparent_pixels += sum(
            reconstructed[index] == 0
            for index in range(3, stride, 4)
        )
        previous = reconstructed

    return width, height, transparent_pixels


def test_approved_logo_sources_are_unchanged_rgba_pngs_with_transparency():
    for filename, expected in _APPROVED_LOGOS.items():
        payload = (_IMAGE_DIRECTORY / filename).read_bytes()
        width, height, transparent_pixels = _rgba_png_details(payload)

        assert hashlib.sha256(payload).hexdigest() == expected["sha256"]
        assert (width, height) == (1024, 1024)
        assert transparent_pixels == expected["transparent_pixels"]
        assert transparent_pixels > 0


def test_desktop_hero_and_mobile_header_use_approved_logo_variants(client):
    landing = client.get("/").get_data(as_text=True)

    assert landing.count('src="/static/img/logo_blue.png"') == 1
    assert landing.count('src="/static/img/logo_silver.png"') == 1
    assert 'class="brand"' not in landing
    assert 'class="brand__name"' not in landing
    assert (
        '<h1 id="page-title" class="landing-brand__name">CryoCheck</h1>'
        in landing
    )
    assert "favicon.svg" not in landing
    assert "&#10052;" not in landing


def test_logo_css_preserves_artwork_without_boxes_filters_or_clipping():
    stylesheet = Path("app/static/css/app.css").read_text(encoding="utf-8")
    selectors = (
        ".landing-brand__mark",
        ".mobile-brand img",
    )

    for selector in selectors:
        match = re.search(
            rf"{re.escape(selector)}\s*\{{(?P<rules>[^}}]+)\}}",
            stylesheet,
        )
        assert match is not None
        rules = match.group("rules")
        assert "object-fit: contain" in rules
        assert "filter:" not in rules
        assert "background:" not in rules
        assert "overflow:" not in rules


def test_favicon_apple_windows_and_pwa_metadata_use_final_assets(client):
    landing = client.get("/").get_data(as_text=True)

    assert 'href="/favicon.ico"' in landing
    assert 'href="/static/img/favicon-16x16.png"' in landing
    assert 'sizes="16x16"' in landing
    assert 'href="/static/img/favicon-32x32.png"' in landing
    assert 'sizes="32x32"' in landing
    assert 'href="/static/img/icon-180.png"' in landing
    assert 'sizes="180x180"' in landing
    assert 'name="msapplication-TileColor" content="#071b33"' in landing
    assert re.search(
        r'name="msapplication-TileImage"\s+'
        r'content="/static/img/mstile-150x150\.png"',
        landing,
    )

    manifest = json.loads(
        client.get("/static/manifest.webmanifest").get_data(as_text=True)
    )
    assert manifest["icons"] == [
        {
            "src": "/static/img/icon-192.png",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any",
        },
        {
            "src": "/static/img/icon-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any",
        },
        {
            "src": "/static/img/icon-maskable-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "maskable",
        },
        {
            "src": "/static/img/logo_blue.png",
            "sizes": "1024x1024",
            "type": "image/png",
            "purpose": "any",
        },
    ]


def test_all_final_branding_asset_urls_are_available_at_exact_dimensions(client):
    expected_pngs = {
        "/static/img/favicon-16x16.png": (16, 16),
        "/static/img/favicon-32x32.png": (32, 32),
        "/static/img/icon-180.png": (180, 180),
        "/static/img/icon-192.png": (192, 192),
        "/static/img/icon-512.png": (512, 512),
        "/static/img/icon-maskable-512.png": (512, 512),
        "/static/img/logo_blue.png": (1024, 1024),
        "/static/img/logo_silver.png": (1024, 1024),
        "/static/img/mstile-150x150.png": (150, 150),
    }

    for path, dimensions in expected_pngs.items():
        response = client.get(path)
        assert response.status_code == 200
        assert response.mimetype == "image/png"
        assert _rgba_png_details(response.data)[:2] == dimensions

    favicon = client.get("/favicon.ico")
    assert favicon.status_code == 200
    assert favicon.data[:6] == b"\x00\x00\x01\x00\x02\x00"


def test_favicon_ico_contains_16_and_32_pixel_png_fallbacks():
    payload = (_IMAGE_DIRECTORY / "favicon.ico").read_bytes()
    reserved, icon_type, image_count = struct.unpack("<HHH", payload[:6])
    dimensions = set()

    assert (reserved, icon_type, image_count) == (0, 1, 2)
    for index in range(image_count):
        entry_offset = 6 + (index * 16)
        (
            width,
            height,
            _colors,
            _reserved,
            planes,
            bit_count,
            size,
            image_offset,
        ) = struct.unpack(
            "<BBBBHHII",
            payload[entry_offset : entry_offset + 16],
        )
        dimensions.add((width or 256, height or 256))
        assert planes == 1
        assert bit_count == 32
        assert payload[image_offset : image_offset + 8] == (
            b"\x89PNG\r\n\x1a\n"
        )
        assert image_offset + size <= len(payload)

    assert dimensions == {(16, 16), (32, 32)}


def test_service_worker_cache_is_versioned_and_static_only(client):
    script = client.get("/service-worker.js").get_data(as_text=True)
    asset_block = re.search(
        r"const APP_SHELL_ASSETS = \[(.*?)\];",
        script,
        flags=re.DOTALL,
    )

    assert 'const CACHE_NAME = "cryocheck-static-shell-v9";' in script
    assert asset_block is not None
    assets = set(re.findall(r'"([^"]+)"', asset_block.group(1)))
    assert {
        "/static/img/favicon.ico",
        "/static/img/favicon-16x16.png",
        "/static/img/favicon-32x32.png",
        "/static/img/icon-180.png",
        "/static/img/icon-192.png",
        "/static/img/icon-512.png",
        "/static/img/icon-maskable-512.png",
        "/static/img/logo_blue.png",
        "/static/img/logo_silver.png",
        "/static/img/mstile-150x150.png",
    } <= assets
    assert all(asset.startswith("/static/") for asset in assets)
    assert 'event.request.method === "GET"' in script
    assert "APP_SHELL_PATHS.has(requestUrl.pathname)" in script
