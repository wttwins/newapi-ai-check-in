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


class TopicTimeline:
    async def inner_text(self):
        return '1 / 1'


class ChangingTimelineElement:
    def __init__(self, values):
        self.values = values
        self.index = 0

    async def inner_text(self):
        value = self.values[min(self.index, len(self.values) - 1)]
        self.index += 1
        return value


class ScrollReadPage:
    def __init__(self, timeline_values):
        self.timeline = ChangingTimelineElement(timeline_values)
        self.scroll_calls = 0
        self.bottom_force_calls = 0

    async def evaluate(self, script):
        if script == 'window.scrollBy(0, window.innerHeight)':
            self.scroll_calls += 1
            return None
        if script == 'window.scrollTo(0, document.body.scrollHeight)':
            self.bottom_force_calls += 1
            return None
        raise AssertionError(f'unexpected script: {script}')

    async def wait_for_timeout(self, ms):
        return None

    async def query_selector(self, selector):
        if selector == '.timeline-replies':
            return self.timeline
        return None


class DeepLinkUnreadPage:
    def __init__(self):
        self.url = 'about:blank'
        self.goto_calls = []
        self.current_page = 'unread'

    async def goto(self, url, wait_until=None):
        self.url = url
        self.goto_calls.append((url, wait_until))
        if '/unread' in url:
            self.current_page = 'unread'
        elif '/t/' in url:
            self.current_page = 'topic'

    async def wait_for_timeout(self, ms):
        return None

    async def wait_for_selector(self, selector, timeout=None):
        return None

    async def evaluate(self, script):
        if 'querySelectorAll' in script:
            return ['https://linux.do/t/topic/1170760/1948']
        raise AssertionError(f'unexpected script: {script}')

    async def query_selector(self, selector):
        if selector == '.timeline-replies' and self.current_page == 'topic':
            return TopicTimeline()
        return None

    async def title(self):
        return 'Unread'

    async def content(self):
        return '<html></html>'

    async def close(self):
        return None


class LimitedUnreadPage:
    def __init__(self):
        self.url = 'about:blank'
        self.goto_calls = []
        self.current_page = 'unread'

    async def goto(self, url, wait_until=None):
        self.url = url
        self.goto_calls.append((url, wait_until))
        if '/unread' in url:
            self.current_page = 'unread'
        elif '/t/' in url:
            self.current_page = 'topic'

    async def wait_for_timeout(self, ms):
        return None

    async def wait_for_selector(self, selector, timeout=None):
        return None

    async def evaluate(self, script):
        if 'querySelectorAll' in script:
            return [
                'https://linux.do/t/topic/100001',
                'https://linux.do/t/topic/100002',
                'https://linux.do/t/topic/100003',
                'https://linux.do/t/topic/100004',
            ]
        raise AssertionError(f'unexpected script: {script}')

    async def query_selector(self, selector):
        if selector == '.timeline-replies' and self.current_page == 'topic':
            return TopicTimeline()
        return None

    async def title(self):
        return 'Unread'

    async def content(self):
        return '<html></html>'

    async def close(self):
        return None


class ReplyFilteredUnreadPage:
    def __init__(self):
        self.url = 'about:blank'
        self.goto_calls = []
        self.current_page = 'unread'

    async def goto(self, url, wait_until=None):
        self.url = url
        self.goto_calls.append((url, wait_until))
        if '/unread' in url:
            self.current_page = 'unread'
        elif '/t/' in url:
            self.current_page = 'topic'

    async def wait_for_timeout(self, ms):
        return None

    async def wait_for_selector(self, selector, timeout=None):
        return None

    async def evaluate(self, script):
        if 'has_login_icon' in script:
            raise AssertionError(f'unexpected login script: {script}')
        if 'replyCount' in script:
            return [
                {'url': 'https://linux.do/t/topic/200001', 'replyCount': 800},
                {'url': 'https://linux.do/t/topic/200002', 'replyCount': 499},
                {'url': 'https://linux.do/t/topic/200003', 'replyCount': 500},
            ]
        if 'querySelectorAll' in script:
            return [
                'https://linux.do/t/topic/200001',
                'https://linux.do/t/topic/200002',
                'https://linux.do/t/topic/200003',
            ]
        raise AssertionError(f'unexpected script: {script}')

    async def query_selector(self, selector):
        if selector == '.timeline-replies' and self.current_page == 'topic':
            return TopicTimeline()
        return None

    async def title(self):
        return 'Unread'

    async def content(self):
        return '<html></html>'

    async def inner_text(self, selector=None):
        return 'body'

    async def close(self):
        return None


class LoginStatePage:
    def __init__(self, has_login_icon: bool, has_avatar: bool, url: str = 'about:blank', title_text: str = 'Linux Do'):
        self.url = url
        self.has_login_icon = has_login_icon
        self.has_avatar = has_avatar
        self.title_text = title_text

    async def goto(self, url, wait_until=None):
        self.url = url

    async def wait_for_timeout(self, ms):
        return None

    async def evaluate(self, script):
        if 'has_login_icon' in script and 'has_avatar' in script:
            return {
                'has_login_icon': self.has_login_icon,
                'has_avatar': self.has_avatar,
            }
        raise AssertionError(f'unexpected script: {script}')

    async def title(self):
        return self.title_text


class NotFoundUnreadPage:
    def __init__(self):
        self.url = 'about:blank'

    async def goto(self, url, wait_until=None):
        self.url = url

    async def wait_for_timeout(self, ms):
        return None

    async def wait_for_selector(self, selector, timeout=None):
        return None

    async def evaluate(self, script):
        if 'has_login_icon' in script and 'has_avatar' in script:
            return {'has_login_icon': False, 'has_avatar': True}
        if 'querySelectorAll' in script:
            return []
        raise AssertionError(f'unexpected script: {script}')

    async def title(self):
        return 'Page Not Found - LINUX DO'

    async def content(self):
        return '<div class="page-not-found-topics"></div>'

    async def inner_text(self, selector=None):
        return 'Oops! That page doesn’t exist or is private.'

    async def close(self):
        return None


class ReadPostsDebugTests(unittest.IsolatedAsyncioTestCase):
    async def test_scroll_to_read_raises_when_progress_does_not_grow_for_30s(self):
        page = ScrollReadPage(['399 / 401'] * 20)
        reader = LinuxDoReadPosts('tester@example.com', 'secret')

        original_randint = module_under_test.random.randint
        module_under_test.random.randint = lambda a, b: 3000

        try:
            with self.assertRaisesRegex(RuntimeError, 'Scroll progress stalled for 30s'):
                await reader._scroll_to_read(page)
        finally:
            module_under_test.random.randint = original_randint

    async def test_scroll_to_read_forces_bottom_scroll_when_progress_stalls_before_completion(self):
        page = ScrollReadPage(['1 / 401', '399 / 401', '399 / 401', '401 / 401'])
        reader = LinuxDoReadPosts('tester@example.com', 'secret')

        original_randint = module_under_test.random.randint
        module_under_test.random.randint = lambda a, b: a

        try:
            await reader._scroll_to_read(page)
        finally:
            module_under_test.random.randint = original_randint

        self.assertEqual(page.bottom_force_calls, 1)
        self.assertGreaterEqual(page.scroll_calls, 3)

    async def test_scroll_to_read_does_not_stop_until_progress_reaches_x_over_x(self):
        page = ScrollReadPage(['1 / 86', '1 / 86', '1 / 86', '86 / 86'])
        reader = LinuxDoReadPosts('tester@example.com', 'secret')

        original_randint = module_under_test.random.randint
        module_under_test.random.randint = lambda a, b: a

        try:
            await reader._scroll_to_read(page)
        finally:
            module_under_test.random.randint = original_randint

        self.assertEqual(page.scroll_calls, 4)

    async def test_run_returns_error_when_unread_page_is_not_found(self):
        page = NotFoundUnreadPage()
        reader = LinuxDoReadPosts('tester@example.com', 'secret')

        original_getenv = module_under_test.os.getenv
        original_async_camoufox = module_under_test.AsyncCamoufox
        original_exists = module_under_test.os.path.exists
        original_ensure = module_under_test.ensure_storage_state_from_env
        original_normalize = module_under_test.normalize_storage_state_file

        class FakeContext:
            async def new_page(self):
                return page

            async def storage_state(self, path=None):
                return None

            async def close(self):
                return None

        class FakeBrowser:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def new_context(self, storage_state=None):
                return FakeContext()

        def fake_async_camoufox(*args, **kwargs):
            return FakeBrowser()

        def fake_getenv(name, default=None):
            if name == 'LINUXDO_MAX_POSTS':
                return '1'
            return original_getenv(name, default)

        module_under_test.os.getenv = fake_getenv
        module_under_test.AsyncCamoufox = fake_async_camoufox
        module_under_test.os.path.exists = lambda path: False
        module_under_test.ensure_storage_state_from_env = lambda *args, **kwargs: False
        module_under_test.normalize_storage_state_file = lambda *args, **kwargs: False

        try:
            success, result = await reader.run()
        finally:
            module_under_test.os.getenv = original_getenv
            module_under_test.AsyncCamoufox = original_async_camoufox
            module_under_test.os.path.exists = original_exists
            module_under_test.ensure_storage_state_from_env = original_ensure
            module_under_test.normalize_storage_state_file = original_normalize

        self.assertFalse(success)
        self.assertIn('Unread page unavailable', result['error'])

    async def test_is_logged_in_returns_false_when_login_icon_is_visible(self):
        page = LoginStatePage(has_login_icon=True, has_avatar=False)
        reader = LinuxDoReadPosts('tester@example.com', 'secret')

        self.assertFalse(await reader._is_logged_in(page))

    async def test_is_logged_in_returns_true_when_avatar_is_visible(self):
        page = LoginStatePage(has_login_icon=False, has_avatar=True)
        reader = LinuxDoReadPosts('tester@example.com', 'secret')

        self.assertTrue(await reader._is_logged_in(page))

    async def test_is_logged_in_saves_debug_artifacts_when_state_is_undetermined(self):
        page = LoginStatePage(has_login_icon=False, has_avatar=False, url='https://linux.do/')
        reader = LinuxDoReadPosts('tester@example.com', 'secret')

        original_save_page_content = module_under_test.save_page_content_to_file
        original_take_screenshot = module_under_test.take_screenshot
        save_page_content_mock = AsyncMock()
        take_screenshot_mock = AsyncMock()
        module_under_test.save_page_content_to_file = save_page_content_mock
        module_under_test.take_screenshot = take_screenshot_mock

        try:
            result = await reader._is_logged_in(page)
        finally:
            module_under_test.save_page_content_to_file = original_save_page_content
            module_under_test.take_screenshot = original_take_screenshot

        self.assertFalse(result)
        save_page_content_mock.assert_awaited_once_with(page, 'login_state_undetermined', reader.username)
        take_screenshot_mock.assert_awaited_once_with(page, 'login_state_undetermined', reader.username)

    async def test_read_posts_selects_only_topics_with_reply_count_below_500(self):
        page = ReplyFilteredUnreadPage()
        reader = LinuxDoReadPosts('tester@example.com', 'secret')

        original_choice = module_under_test.random.choice
        original_randint = module_under_test.random.randint
        module_under_test.random.choice = lambda items: items[0]
        module_under_test.random.randint = lambda a, b: a

        try:
            last_topic_url, read_count = await reader._read_posts(page, 1)
        finally:
            module_under_test.random.choice = original_choice
            module_under_test.random.randint = original_randint

        self.assertEqual(read_count, 1)
        self.assertEqual(last_topic_url, 'https://linux.do/t/topic/200002')
        self.assertIn(('https://linux.do/t/topic/200002', 'domcontentloaded'), page.goto_calls)
        self.assertNotIn(('https://linux.do/t/topic/200001', 'domcontentloaded'), page.goto_calls)
        self.assertNotIn(('https://linux.do/t/topic/200003', 'domcontentloaded'), page.goto_calls)

    async def test_run_uses_exact_env_max_posts_without_random_range(self):
        page = LimitedUnreadPage()
        reader = LinuxDoReadPosts('tester@example.com', 'secret')

        original_getenv = module_under_test.os.getenv
        original_async_camoufox = module_under_test.AsyncCamoufox
        original_exists = module_under_test.os.path.exists
        original_ensure = module_under_test.ensure_storage_state_from_env
        original_normalize = module_under_test.normalize_storage_state_file

        class FakeContext:
            async def new_page(self):
                return page

            async def storage_state(self, path=None):
                return None

            async def close(self):
                return None

        class FakeBrowser:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

            async def new_context(self, storage_state=None):
                return FakeContext()

        def fake_async_camoufox(*args, **kwargs):
            return FakeBrowser()

        def fake_getenv(name, default=None):
            if name == 'LINUXDO_MAX_POSTS':
                return '3'
            return original_getenv(name, default)

        reader._is_logged_in = types.MethodType(AsyncMock(return_value=True), reader)

        module_under_test.os.getenv = fake_getenv
        module_under_test.AsyncCamoufox = fake_async_camoufox
        module_under_test.os.path.exists = lambda path: False
        module_under_test.ensure_storage_state_from_env = lambda *args, **kwargs: False
        module_under_test.normalize_storage_state_file = lambda *args, **kwargs: False

        try:
            success, result = await reader.run()
        finally:
            module_under_test.os.getenv = original_getenv
            module_under_test.AsyncCamoufox = original_async_camoufox
            module_under_test.os.path.exists = original_exists
            module_under_test.ensure_storage_state_from_env = original_ensure
            module_under_test.normalize_storage_state_file = original_normalize

        self.assertTrue(success)
        self.assertEqual(result['read_count'], 3)
        topic_gotos = [url for url, _ in page.goto_calls if '/t/' in url]
        self.assertEqual(len(topic_gotos), 3)

    async def test_read_posts_normalizes_deep_unread_topic_links_before_navigation(self):
        page = DeepLinkUnreadPage()
        reader = LinuxDoReadPosts('tester@example.com', 'secret')

        original_choice = module_under_test.random.choice
        original_randint = module_under_test.random.randint
        module_under_test.random.choice = lambda items: items[0]
        module_under_test.random.randint = lambda a, b: a

        try:
            last_topic_url, read_count = await reader._read_posts(page, 1)
        finally:
            module_under_test.random.choice = original_choice
            module_under_test.random.randint = original_randint

        self.assertEqual(read_count, 1)
        self.assertEqual(last_topic_url, 'https://linux.do/t/topic/1170760')
        self.assertIn(('https://linux.do/t/topic/1170760', 'domcontentloaded'), page.goto_calls)
        self.assertNotIn(('https://linux.do/t/topic/1170760/1948', 'domcontentloaded'), page.goto_calls)

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
