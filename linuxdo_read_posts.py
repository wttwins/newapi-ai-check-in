#!/usr/bin/env python3
"""
使用 Camoufox 登录 Linux.do 并浏览帖子
"""

import asyncio
import hashlib
import json
import os
import sys
import random
from datetime import datetime
from dotenv import load_dotenv
from camoufox.async_api import AsyncCamoufox
from utils.browser_utils import take_screenshot, save_page_content_to_file
from utils.notify import notify
from utils.mask_utils import mask_username

# 默认缓存目录，与 checkin.py 保持一致
DEFAULT_STORAGE_STATE_DIR = "storage-states"

# 默认最大浏览帖子数
# 通过 LINUXDO_MAX_POSTS 环境变量设置自定义值
DEFAULT_MAX_POSTS = 100


class LinuxDoReadPosts:
    """Linux.do 帖子浏览类"""

    def __init__(
        self,
        username: str,
        password: str,
        storage_state_dir: str = DEFAULT_STORAGE_STATE_DIR,
    ):
        """初始化

        Args:
            username: Linux.do 用户名
            password: Linux.do 密码
            storage_state_dir: 缓存目录，默认与 checkin.py 共享
        """
        self.username = username
        self.password = password
        self.masked_username = mask_username(username)  # 用于日志输出的掩码用户名
        self.storage_state_dir = storage_state_dir
        # 使用用户名哈希生成缓存文件名，与 checkin.py 保持一致
        self.username_hash = hashlib.sha256(username.encode("utf-8")).hexdigest()[:8]

        os.makedirs(self.storage_state_dir, exist_ok=True)

    async def _is_logged_in(self, page) -> bool:
        """检查是否已登录

        通过访问 https://linux.do/ 后检查 URL 是否跳转到登录页面来判断

        Args:
            page: Camoufox 页面对象

        Returns:
            是否已登录
        """
        try:
            print(f"ℹ️ {self.masked_username}: Checking login status...")
            await page.goto("https://linux.do/", wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)  # 等待可能的重定向

            current_url = page.url
            print(f"ℹ️ {self.masked_username}: Current URL: {current_url}")

            # 如果跳转到登录页面，说明未登录
            if current_url.startswith("https://linux.do/login"):
                print(f"ℹ️ {self.masked_username}: Redirected to login page, not logged in")
                return False

            print(f"✅ {self.masked_username}: Already logged in")
            return True
        except Exception as e:
            print(f"⚠️ {self.masked_username}: Error checking login status: {e}")
            return False

    async def _do_login(self, page) -> bool:
        """执行登录流程

        Args:
            page: Camoufox 页面对象

        Returns:
            登录是否成功
        """
        try:
            print(f"ℹ️ {self.masked_username}: Starting login process...")

            # 如果当前不在登录页面，先导航到登录页面
            if not page.url.startswith("https://linux.do/login"):
                await page.goto("https://linux.do/login", wait_until="domcontentloaded")

            await page.wait_for_timeout(2000)

            # 填写用户名
            await page.fill("#login-account-name", self.username)
            await page.wait_for_timeout(2000)

            # 填写密码
            await page.fill("#login-account-password", self.password)
            await page.wait_for_timeout(2000)

            # 点击登录按钮
            await page.click("#login-button")
            await page.wait_for_timeout(10000)

            await save_page_content_to_file(page, "login_result", self.username)

            # 检查是否遇到 Cloudflare 验证
            current_url = page.url
            print(f"ℹ️ {self.masked_username}: URL after login: {current_url}")

            if "linux.do/challenge" in current_url:
                print(
                    f"⚠️ {self.masked_username}: Cloudflare challenge detected, "
                    "Camoufox should bypass it automatically. Waiting..."
                )
                # 等待 Cloudflare 验证完成，最多等待60秒
                try:
                    await page.wait_for_url("https://linux.do/", timeout=60000)
                    print(f"✅ {self.masked_username}: Cloudflare challenge bypassed")
                except Exception:
                    print(f"⚠️ {self.masked_username}: Cloudflare challenge timeout")

            # 再次检查是否登录成功
            current_url = page.url
            if current_url.startswith("https://linux.do/login"):
                print(f"❌ {self.masked_username}: Login failed, still on login page")
                await take_screenshot(page, "login_failed", self.username)
                return False

            print(f"✅ {self.masked_username}: Login successful")
            return True

        except Exception as e:
            print(f"❌ {self.masked_username}: Error during login: {e}")
            await take_screenshot(page, "login_error", self.username)
            return False

    async def _read_posts(self, page, max_posts: int) -> tuple[str, int]:
        """从 /unread 页面随机选择帖子并阅读

        Args:
            page: Camoufox 页面对象
            max_posts: 最大浏览帖子数

        Returns:
            (最后阅读的帖子URL, 实际阅读数量)
        """
        unread_url = "https://linux.do/unread"
        read_count = 0
        last_topic_url = ""
        visited_urls = set()
        consecutive_empty_count = 0

        while read_count < max_posts:
            await page.goto(unread_url, wait_until="domcontentloaded")
            await page.wait_for_timeout(random.randint(2000, 4000))

            topic_urls = await page.evaluate(
                """() => {
                    const anchors = Array.from(document.querySelectorAll('a[href*="/t/"]'));
                    const urls = [];
                    for (const a of anchors) {
                        const href = a.href || '';
                        if (!href.startsWith('https://linux.do/t/')) continue;
                        try {
                            const url = new URL(href);
                            const parts = url.pathname.split('/').filter(Boolean);
                            if (parts.length < 3 || parts[0] !== 't') continue;
                            if (!parts[2].split('').every(ch => ch >= '0' && ch <= '9')) continue;
                            urls.push(url.origin + url.pathname);
                        } catch (_) {}
                    }
                    return [...new Set(urls)];
                }"""
            )

            available_urls = [url for url in topic_urls if url not in visited_urls]
            if not available_urls:
                consecutive_empty_count += 1
                print(
                    f"⚠️ {self.masked_username}: No unread topic links available on /unread "
                    f"(attempt {consecutive_empty_count})"
                )
                if consecutive_empty_count >= 3:
                    print(f"ℹ️ {self.masked_username}: No more unread topics, stopping")
                    break
                await page.wait_for_timeout(random.randint(2000, 4000))
                continue

            consecutive_empty_count = 0
            topic_url = random.choice(available_urls)
            visited_urls.add(topic_url)
            last_topic_url = topic_url

            try:
                print(f"ℹ️ {self.masked_username}: Opening unread topic {topic_url}...")
                await page.goto(topic_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

                timeline_element = await page.query_selector(".timeline-replies")
                if not timeline_element:
                    print(f"⚠️ {self.masked_username}: Topic page missing timeline, skipping...")
                    await take_screenshot(page, "unread_topic_missing_timeline", self.username)
                    continue

                inner_text = await timeline_element.inner_text()
                print(f"✅ {self.masked_username}: Topic progress: {inner_text.strip()}")

                try:
                    parts = inner_text.strip().split("/")
                    if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                        current_page = int(parts[0].strip())
                        total_pages = int(parts[1].strip())
                        if current_page < total_pages:
                            print(
                                f"ℹ️ {self.masked_username}: Scrolling to read "
                                f"remaining {total_pages - current_page} pages..."
                            )
                            await self._scroll_to_read(page)
                    else:
                        print(f"⚠️ {self.masked_username}: Timeline read error(content: {inner_text}), continue")
                        continue
                except (ValueError, IndexError) as e:
                    print(f"⚠️ {self.masked_username}: Failed to parse progress: {e}")
                    continue

                read_count += 1
                remaining_read_count = max(0, max_posts - read_count)
                print(
                    f"ℹ️ {self.masked_username}: {read_count} topic(s) read, "
                    f"{remaining_read_count} remaining..."
                )
                await page.wait_for_timeout(random.randint(1000, 2000))

            except Exception as e:
                print(f"⚠️ {self.masked_username}: Error reading topic {topic_url}: {e}")
                await take_screenshot(page, "unread_topic_read_error", self.username)

        return last_topic_url, read_count

    async def _scroll_to_read(self, page) -> None:
        """自动滚动浏览帖子内容

        根据 timeline-replies 元素内容判断是否已到底部

        Args:
            page: Camoufox 页面对象
        """
        last_current_page = 0
        last_total_pages = 0

        while True:
            # 执行滚动
            await page.evaluate("window.scrollBy(0, window.innerHeight)")

            # 每次滚动后等待 1-3 秒，模拟阅读
            await page.wait_for_timeout(random.randint(1000, 3000))

            # 检查 timeline-replies 内容判断是否到底
            timeline_element = await page.query_selector(".timeline-replies")
            if not timeline_element:
                print(f"ℹ️ {self.masked_username}: Timeline element not found, stopping")
                break

            inner_html = await timeline_element.inner_text()
            try:
                parts = inner_html.strip().split("/")
                if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                    current_page = int(parts[0].strip())
                    total_pages = int(parts[1].strip())

                    # 如果滚动后页数没变，说明已经到底了
                    if current_page == last_current_page and total_pages == last_total_pages:
                        print(
                            f"ℹ️ {self.masked_username}: Page not changing " f"({current_page}/{total_pages}), reached bottom"
                        )
                        break

                    # 如果当前页等于总页数，说明到底了
                    if current_page >= total_pages:
                        print(f"ℹ️ {self.masked_username}: Reached end " f"({current_page}/{total_pages}) after scrolling")
                        break

                    # 缓存当前页数
                    last_current_page = current_page
                    last_total_pages = total_pages
                else:
                    print(f"ℹ️ {self.masked_username}: Timeline read error(content: {inner_html}), stopping")
                    break
            except (ValueError, IndexError):
                pass

    async def run(self) -> tuple[bool, dict]:
        """执行浏览帖子任务

        Returns:
            (成功标志, 结果信息字典)
        """
        print(f"ℹ️ {self.masked_username}: Starting Linux.do read posts task")

        # 缓存文件路径，与 checkin.py 保持一致
        cache_file_path = f"{self.storage_state_dir}/linuxdo_{self.username_hash}_storage_state.json"

        # 从环境变量获取最大浏览帖子数，并在上下 50 范围内随机
        max_posts_str = os.getenv("LINUXDO_MAX_POSTS", "")
        try:
            base_max_posts = int(max_posts_str) if max_posts_str else DEFAULT_MAX_POSTS
        except ValueError:
            print(
                f"⚠️ {self.masked_username}: Invalid LINUXDO_MAX_POSTS={max_posts_str}, "
                f"fallback to default {DEFAULT_MAX_POSTS}"
            )
            base_max_posts = DEFAULT_MAX_POSTS

        min_posts = max(10, base_max_posts - 50)
        max_posts_upper = max(min_posts, base_max_posts + 50)
        max_posts = random.randint(min_posts, max_posts_upper)
        print(
            f"ℹ️ {self.masked_username}: Max posts range {min_posts}-{max_posts_upper}, "
            f"selected {max_posts}"
        )

        async with AsyncCamoufox(
            headless=False,
            humanize=True,
            locale="en-US",
        ) as browser:
            # 加载缓存的 storage state（如果存在）
            storage_state = cache_file_path if os.path.exists(cache_file_path) else None
            if storage_state:
                print(f"ℹ️ {self.masked_username}: Restoring storage state from cache")
            else:
                print(f"ℹ️ {self.masked_username}: No cache file found, starting fresh")

            context = await browser.new_context(storage_state=storage_state)
            page = await context.new_page()

            try:
                # 检查是否已登录
                is_logged_in = await self._is_logged_in(page)

                # 如果未登录，执行登录流程
                if not is_logged_in:
                    login_success = await self._do_login(page)
                    if not login_success:
                        return False, {"error": "Login failed"}

                    # 保存会话状态
                    await context.storage_state(path=cache_file_path)
                    print(f"✅ {self.masked_username}: Storage state saved to cache file")

                # 浏览帖子
                print(f"ℹ️ {self.masked_username}: Starting to read posts...")
                last_topic_url, read_count = await self._read_posts(page, max_posts)

                print(f"✅ {self.masked_username}: Successfully read {read_count} posts")
                return True, {
                    "read_count": read_count,
                    "last_topic_url": last_topic_url,
                }

            except Exception as e:
                print(f"❌ {self.masked_username}: Error occurred: {e}")
                await take_screenshot(page, "error", self.username)
                return False, {"error": str(e)}
            finally:
                await page.close()
                await context.close()


def load_linuxdo_accounts() -> list[dict]:
    """从 ACCOUNTS 环境变量加载 Linux.do 账号

    Returns:
        包含 linux.do 账号信息的列表，每个元素为:
        {"username": str, "password": str}
    """
    accounts_str = os.getenv("ACCOUNTS")
    if not accounts_str:
        print("❌ ACCOUNTS environment variable not found")
        return []

    try:
        accounts_data = json.loads(accounts_str)

        if not isinstance(accounts_data, list):
            print("❌ ACCOUNTS must be a JSON array")
            return []

        linuxdo_accounts = []
        seen_usernames = set()

        for i, account in enumerate(accounts_data):
            if not isinstance(account, dict):
                print(f"⚠️ ACCOUNTS[{i}] must be a dictionary, skipping")
                continue

            username = account.get("username")
            masked_username = mask_username(username)
            password = account.get("password")

            if not username or not password:
                print(f"⚠️ ACCOUNTS[{i}] missing username or password, skipping")
                continue

            # 根据 username 去重
            if username in seen_usernames:
                print(f"ℹ️ Skipping duplicate account: {masked_username}")
                continue

            seen_usernames.add(username)
            linuxdo_accounts.append(
                {
                    "username": username,
                    "password": password,
                }
            )

        return linuxdo_accounts

    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse ACCOUNTS: {e}")
        return []
    except Exception as e:
        print(f"❌ Error loading ACCOUNTS: {e}")
        return []


async def main():
    """主函数"""
    load_dotenv(override=True)

    print("🚀 Linux.do read posts script started")
    print(f'🕒 Execution time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

    # 加载配置了 linux.do 的账号
    accounts = load_linuxdo_accounts()

    if not accounts:
        print("❌ No accounts with linux.do configuration found")
        return

    print(f"ℹ️ Found {len(accounts)} account(s) with linux.do configuration")

    # 收集结果用于通知
    results = []

    # 为每个账号执行任务
    for account in accounts:
        username = account["username"]
        masked_username = mask_username(username)
        password = account["password"]

        print(f"\n{'='*50}")
        print(f"📌 Processing: {masked_username}")
        print(f"{'='*50}")

        try:
            reader = LinuxDoReadPosts(
                username=username,
                password=password,
            )

            start_time = datetime.now()
            success, result = await reader.run()
            end_time = datetime.now()
            duration = end_time - start_time

            # 格式化时长为 HH:MM:SS
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            print(f"Result: success={success}, result={result}, duration={duration_str}")

            # 记录结果
            results.append(
                {
                    "username": username,
                    "success": success,
                    "result": result,
                    "duration": duration_str,
                }
            )
        except Exception as e:
            print(f"❌ {masked_username}: Exception occurred: {e}")
            results.append(
                {
                    "username": username,
                    "success": False,
                    "result": {"error": str(e)},
                    "duration": "00:00:00",
                }
            )

    # 发送通知
    if results:
        notification_lines = [
            f'🕒 Execution time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
            "",
        ]

        total_read_count = 0
        for r in results:
            username = r["username"]
            masked_username = mask_username(username)
            duration = r["duration"]
            if r["success"]:
                read_count = r["result"].get("read_count", 0)
                total_read_count += read_count
                last_topic_url = r["result"].get("last_topic_url", "unknown")
                notification_lines.append(
                    f"✅ {masked_username}: Read {read_count} posts ({duration})\n" f"   Last topic: {last_topic_url}"
                )
            else:
                error = r["result"].get("error", "Unknown error")
                notification_lines.append(f"❌ {masked_username}: {error} ({duration})")

        # 添加阅读总数
        notification_lines.append("")
        notification_lines.append(f"📊 Total read: {total_read_count} posts")

        notify_content = "\n".join(notification_lines)
        notify.push_message("Linux.do Read Posts", notify_content, msg_type="text")


def run_main():
    """运行主函数的包装函数"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Program interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error occurred during program execution: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_main()
