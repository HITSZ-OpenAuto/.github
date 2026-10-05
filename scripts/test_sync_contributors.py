import io
import json
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import Mock
from urllib.error import URLError

from PIL import Image

import sync_contributors as sync


def user(login="alice", kind="User"):
    return {
        "login": login,
        "type": kind,
        "avatar_url": "https://avatars.githubusercontent.com/u/123?v=4",
        "contributions": 1,
    }


def png(color="red"):
    result = io.BytesIO()
    Image.new("RGBA", (180, 150), color).save(result, "PNG")
    return result.getvalue()


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "profile").mkdir()
        self.readme = self.root / "profile/README.md"
        self.before = "用户内容\r\n" + sync.START + "\nold content\n" + sync.END + "\r\n尾部\n"
        self.readme.write_bytes(self.before.encode())
        self.users = [user("z-first"), user("alice"), user("dependabot[bot]", "Bot")]
        self.avatar = png()

    def fetch(self, url):
        return json.dumps(self.users).encode() if url == sync.API_URL else self.avatar

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def test_order_filters_bots_and_non_generated_content_are_preserved(self):
        count, changed = sync.sync(self.root, self.fetch)
        self.assertEqual((count, changed), (3, True))
        content = self.readme.read_bytes().decode()
        self.assertTrue(content.startswith("用户内容\r\n"))
        self.assertTrue(content.endswith("\r\n尾部\n"))
        self.assertLess(content.index('alt="@z-first"'), content.index('alt="@alice"'))
        self.assertIn('href="https://github.com/apps/dependabot"', content)
        self.assertIn("dependabot%5Bbot%5D.png", content)
        self.assertEqual(sync.API_URL, "https://contrib.hoa.moe/api/json?org=HITSZ-OpenAuto&exclude=.github&repo=noname7321/HITSZ-OpenAuto")

    def test_second_run_is_byte_for_byte_no_op(self):
        sync.sync(self.root, self.fetch)
        before = self.snapshot()
        mtimes = {p: p.stat().st_mtime_ns for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(sync.sync(self.root, self.fetch), (3, False))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual({p: p.stat().st_mtime_ns for p in mtimes}, mtimes)

    def test_png_is_circular_transparent_and_deterministic(self):
        result = sync.circular_avatar(self.avatar)
        self.assertEqual(result, sync.circular_avatar(self.avatar))
        image = Image.open(io.BytesIO(result))
        self.assertEqual(image.size, (128, 128))
        self.assertEqual(image.mode, "RGBA")
        for point in [(0, 0), (127, 0), (0, 127), (127, 127)]:
            self.assertEqual(image.getpixel(point)[3], 0)
        self.assertEqual(image.getpixel((64, 64)), (255, 0, 0, 255))

    def test_source_transparency_is_preserved(self):
        image = Image.open(io.BytesIO(sync.circular_avatar(png((255, 0, 0, 100)))))
        self.assertEqual(image.getpixel((64, 64))[3], 100)

    def test_invalid_or_empty_api_never_changes_files(self):
        for data in [[], {}, {"error": "upstream failed"}, None, [None], [user(), user("ALICE")]]:
            with self.subTest(data=data):
                before = self.snapshot()
                with self.assertRaises(ValueError):
                    sync.sync(self.root, lambda _: json.dumps(data).encode())
                self.assertEqual(self.snapshot(), before)

    def test_invalid_json_or_fetch_failure_never_changes_files(self):
        for fetch in [lambda _: b"not JSON", Mock(side_effect=URLError("offline"))]:
            before = self.snapshot()
            with self.assertRaises((ValueError, URLError)):
                sync.sync(self.root, fetch)
            self.assertEqual(self.snapshot(), before)

    def test_avatar_failure_preserves_existing_readme_and_assets(self):
        sync.sync(self.root, self.fetch)
        before = self.snapshot()
        self.users.append(user("new-person"))
        def fetch(url):
            if url == sync.API_URL:
                return json.dumps(self.users).encode()
            raise URLError("avatar download failed")
        with self.assertRaises(URLError):
            sync.sync(self.root, fetch)
        self.assertEqual(self.snapshot(), before)

    def test_invalid_avatar_image_preserves_existing_files(self):
        before = self.snapshot()
        self.avatar = b"not an image"
        with self.assertRaises(OSError):
            sync.sync(self.root, self.fetch)
        self.assertEqual(self.snapshot(), before)

    def test_unsafe_logins_and_avatar_urls_are_rejected(self):
        for login in ['../foo', '<script>', 'a" onclick="x', '', 'a/b', 'a' * 40]:
            with self.subTest(login=login), self.assertRaises(ValueError):
                sync.validate_contributors([user(login)])
        for url in ["https://evil.example/u/1", "http://avatars.githubusercontent.com/u/1", "https://avatars.githubusercontent.com@evil.example/u/1", "https://avatars.githubusercontent.com/u/1#fragment", "https://avatars.githubusercontent.com/../secret", None]:
            item = user()
            item["avatar_url"] = url
            with self.subTest(url=url), self.assertRaises(ValueError):
                sync.validate_contributors([item])

    def test_missing_repeated_or_reversed_markers_abort_before_fetch(self):
        for content in ["no markers", sync.START * 2 + sync.END, sync.END + sync.START]:
            self.readme.write_text(content)
            fetch = Mock()
            with self.assertRaises(ValueError):
                sync.sync(self.root, fetch)
            fetch.assert_not_called()
            self.assertEqual(self.readme.read_text(), content)

    def test_only_stale_generated_pngs_are_removed(self):
        sync.sync(self.root, self.fetch)
        keep = self.root / "images/contributors/README.txt"
        keep.write_text("keep me")
        self.users = self.users[:2]
        sync.sync(self.root, self.fetch)
        self.assertFalse((keep.parent / "dependabot[bot].png").exists())
        self.assertTrue((keep.parent / "alice.png").exists())
        self.assertEqual(keep.read_text(), "keep me")

    def test_only_one_size_parameter_is_requested(self):
        item = user()
        item["avatar_url"] += "&s=64"
        self.assertEqual(sync.avatar_url(item), "https://avatars.githubusercontent.com/u/123?v=4&s=128")

    def test_twelve_avatars_per_row_without_trailing_break(self):
        self.assertEqual(sync.render_block([user(str(i)) for i in range(24)]).count("<br />"), 1)
        self.assertEqual(sync.render_block([user(str(i)) for i in range(25)]).count("<br />"), 2)


class GeneratedAssetsTests(unittest.TestCase):
    def test_committed_grid_links_assets_and_circular_alpha(self):
        from urllib.parse import unquote
        content = (sync.ROOT / "profile/README.md").read_text()
        block = content.split(sync.START)[1].split(sync.END)[0]
        images = []
        class Grid(HTMLParser):
            link = None
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "a":
                    self.link = attrs["href"]
                elif tag == "img":
                    images.append((self.link, attrs))
            def handle_endtag(self, tag):
                if tag == "a":
                    self.link = None
        Grid().feed(block)
        self.assertGreater(len(images), 0)
        names = []
        for link, attrs in images:
            login = attrs["alt"][1:]
            self.assertEqual(link, sync.profile_url(user(login, "Bot" if login.endswith("[bot]") else "User")))
            self.assertEqual((attrs["width"], attrs["height"]), ("64", "64"))
            path = sync.ROOT / "profile" / unquote(attrs["src"])
            names.append(path.name)
            with Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.size, (128, 128))
                self.assertEqual(image.getpixel((0, 0))[3], 0)
                self.assertEqual(image.getpixel((127, 127))[3], 0)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), {p.name for p in (sync.ROOT / "images/contributors").glob("*.png")})


if __name__ == "__main__":
    unittest.main()
