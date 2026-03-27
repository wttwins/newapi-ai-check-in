import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def _install_test_stubs():
    dotenv_module = types.ModuleType('dotenv')
    dotenv_module.load_dotenv = lambda *args, **kwargs: None
    sys.modules['dotenv'] = dotenv_module

    camoufox_module = types.ModuleType('camoufox')
    camoufox_async_api = types.ModuleType('camoufox.async_api')
    camoufox_async_api.AsyncCamoufox = object
    sys.modules['camoufox'] = camoufox_module
    sys.modules['camoufox.async_api'] = camoufox_async_api

    browser_utils = types.ModuleType('utils.browser_utils')

    async def noop_async(*args, **kwargs):
        return None

    browser_utils.take_screenshot = noop_async
    browser_utils.save_page_content_to_file = noop_async
    sys.modules['utils.browser_utils'] = browser_utils

    notify_module = types.ModuleType('utils.notify')
    notify_module.notify = types.SimpleNamespace(push_message=lambda *args, **kwargs: None)
    sys.modules['utils.notify'] = notify_module

    mask_utils = types.ModuleType('utils.mask_utils')
    mask_utils.mask_username = lambda username: username
    sys.modules['utils.mask_utils'] = mask_utils


_install_test_stubs()

import linuxdo_read_posts as module_under_test
from linuxdo_read_posts import LinuxDoReadPosts


class EmptyUnreadPage:
    def __init__(self):
        self.url = 'about:blank'
        self.wait_for_selector_calls = []

    async def goto(self, url, wait_until=None):
        self.url = url

    async def wait_for_timeout(self, ms):
        return None

    async def wait_for_selector(self, selector, timeout=None):
        self.wait_for_selector_calls.append((selector, timeout))
        return None

    async def evaluate(self, script):
        if 'querySelectorAll' in script:
            return []
        raise AssertionError(f'unexpected script: {script}')

    async def title(self):
        return 'Unread'

    async def content(self):
        return '<html><body><div>No topics</div></body></html>'

    async def inner_text(self, selector=None):
        return 'No topics'


class ReadPostsDebugTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_posts_captures_debug_artifacts_when_unread_has_no_matches(self):
        page = EmptyUnreadPage()
        reader = LinuxDoReadPosts('tester@example.com', 'secret')

        save_page = AsyncMock()
        screenshot = AsyncMock()

        original_randint = module_under_test.random.randint
        original_save_page = module_under_test.save_page_content_to_file
        original_screenshot = module_under_test.take_screenshot
        module_under_test.random.randint = lambda a, b: a
        module_under_test.save_page_content_to_file = save_page
        module_under_test.take_screenshot = screenshot

        try:
            last_topic_url, read_count = await reader._read_posts(page, 1)
        finally:
            module_under_test.random.randint = original_randint
            module_under_test.save_page_content_to_file = original_save_page
            module_under_test.take_screenshot = original_screenshot

        self.assertEqual(last_topic_url, '')
        self.assertEqual(read_count, 0)
        self.assertEqual(page.wait_for_selector_calls, [('a[href*="/t/"]', 10000)] * 3)

        save_page.assert_any_await(page, 'unread_page_no_topic_links', 'tester@example.com')
        screenshot.assert_any_await(page, 'unread_page_no_topic_links', 'tester@example.com')


if __name__ == '__main__':
    unittest.main()
