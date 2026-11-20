import requests
import json
import os
import time
import logging
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from pypushdeer import PushDeer
from logging_config import init_logger


class CheckinStatus(Enum):
    """签到状态"""

    SUCCESS = 0
    REPEAT = 1
    FAILURE = -2


class ExchangePlan(Enum):
    """兑换计划"""

    PLAN100 = "plan100"
    PLAN200 = "plan200"
    PLAN500 = "plan500"


class APIEndpoint(Enum):
    """API端点"""

    CHECKIN = "/api/user/checkin"
    STATUS = "/api/user/status"
    POINTS = "/api/user/points"
    EXCHANGE = "/api/user/exchange"


class LogEmoji:
    """日志 Emoji 常量"""

    SUCCESS = "✅"
    FAIL = "❌"
    REPEAT = "🔄"
    PENDING = "⏳"
    CHECKIN = "🎫"
    STATUS = "📊"
    POINTS = "💰"
    EXCHANGE = "🎁"
    START = "🚀"
    END = "🏁"
    COOKIE = "🍪"
    DOMAIN = "🌐"
    WARNING = "⚠️ "
    ERROR = "🔴"
    INFO = "ℹ️ "


def log_method(func):
    """日志装饰器"""

    def wrapper(self, *args, **kwargs):
        method_name = func.__name__
        emoji_map = {
            "checkin": LogEmoji.CHECKIN,
            "get_status": LogEmoji.STATUS,
            "get_points": LogEmoji.POINTS,
            "exchange": LogEmoji.EXCHANGE,
        }
        emoji = emoji_map.get(method_name, LogEmoji.INFO)
        try:
            result = func(self, *args, **kwargs)
            return result
        except Exception as e:
            logger.error(f"{LogEmoji.COOKIE}[{self.cookie_index}] {LogEmoji.DOMAIN}[{self.domain}] {LogEmoji.ERROR} {method_name} 执行失败: {e}")

            DEFAULT_ERRORS = {
                "checkin": {"status": "签到失败", "points": "0", "message": ""},
                "get_status": ("None 天", -2),
                "get_points": ("None 积分", 0),
                "exchange": "",
            }

            if method_name in DEFAULT_ERRORS:
                error_template = DEFAULT_ERRORS[method_name]
                if isinstance(error_template, dict):
                    error_result = error_template.copy()
                    error_result["message"] = f"执行失败: {e}"
                    return error_result
                return error_template
            raise

    return wrapper


class Config:
    """应用配置"""

    ENV_PUSH_KEY = "PUSHDEER_SENDKEY"
    ENV_COOKIES = "GLADOS_COOKIES"
    ENV_COOKIES_2 = "GLADOS_COOKIES_2"
    ENV_EXCHANGE_PLAN = "GLADOS_EXCHANGE_PLAN"
    ENV_VERBOSE = "GLADOS_VERBOSE"

    """自动兑换已关闭：只签到领积分，绝不自动兑换。
    保留 GLADOS_EXCHANGE_PLAN 这个环境变量名只是为了兼容旧配置，
    读到它也会忽略，不会触发任何兑换。需要兑换时请手动在官网操作。"""
    DEFAULT_EXCHANGE_PLAN = "none"

    """默认是否输出详细响应"""
    DEFAULT_VERBOSE = False

    """默认域名：先试 glados.cloud，status 无权限时再试备用域名"""
    DOMAINS = ["glados.cloud", "glados.rocks", "railgun.info"]

    def __init__(self):
        self.push_key: str = ""
        self.cookies_list: List[str] = []
        self.exchange_plan: str = self.DEFAULT_EXCHANGE_PLAN
        self.verbose: bool = self.DEFAULT_VERBOSE
        self._load_config()

    def _load_config(self) -> None:
        """加载配置"""
        push_key_env: Optional[str] = os.environ.get(self.ENV_PUSH_KEY)
        raw_cookies_env: Optional[str] = os.environ.get(self.ENV_COOKIES)
        second_cookies_env: Optional[str] = os.environ.get(self.ENV_COOKIES_2)
        exchange_plan_env: Optional[str] = os.environ.get(self.ENV_EXCHANGE_PLAN)
        verbose_env: Optional[str] = os.environ.get(self.ENV_VERBOSE)

        if not push_key_env:
            logger.warning(f"{LogEmoji.WARNING} 环境变量 '{self.ENV_PUSH_KEY}' 未设置。")
            self.push_key = ""
        else:
            self.push_key = push_key_env

        # 各账号独立配置；继续兼容旧的 & 分隔格式，不记录凭据。
        self.cookies_list = []
        for raw in (raw_cookies_env, second_cookies_env):
            for cookie in (raw or "").split("&"):
                cookie = cookie.strip()
                if cookie and cookie not in self.cookies_list:
                    self.cookies_list.append(cookie)
        if not self.cookies_list:
            logger.warning("未设置有效的 GLADOS_COOKIES 或 GLADOS_COOKIES_2。")

        if not exchange_plan_env:
            logger.info(f"{LogEmoji.INFO} 自动兑换已关闭，只签到领积分，不兑换。")
            self.exchange_plan = self.DEFAULT_EXCHANGE_PLAN
        else:
            logger.info(f"{LogEmoji.INFO} 自动兑换已关闭，忽略 {self.ENV_EXCHANGE_PLAN} 的值，只签到领积分，不兑换。")
            self.exchange_plan = self.DEFAULT_EXCHANGE_PLAN

        logger.info(f"{LogEmoji.INFO} 共加载了 {len(self.cookies_list)} 个 Cookie 用于签到。")
        logger.info(f"{LogEmoji.INFO} 当前 {self.ENV_PUSH_KEY} {'已设置' if push_key_env else '未设置'}。")
        logger.info(f"{LogEmoji.INFO} 当前 {self.ENV_EXCHANGE_PLAN}: {self.exchange_plan}。")

        if verbose_env is not None:
            verbose_env_lower = verbose_env.lower()
            if verbose_env_lower in ["true", "1", "yes", "y"]:
                self.verbose = True
            elif verbose_env_lower in ["false", "0", "no", "n"]:
                self.verbose = False
            else:
                logger.warning(f"{LogEmoji.WARNING} 环境变量 '{self.ENV_VERBOSE}' 的值 '{verbose_env}' 无效，将使用默认值 {self.DEFAULT_VERBOSE}。")

        logger.info(f"{LogEmoji.INFO} 当前 {self.ENV_VERBOSE}: {self.verbose}。")


class API:
    """API 调用"""

    CHECKIN_URL = APIEndpoint.CHECKIN.value
    STATUS_URL = APIEndpoint.STATUS.value
    POINTS_URL = APIEndpoint.POINTS.value
    EXCHANGE_URL = APIEndpoint.EXCHANGE.value

    def __init__(self, domain: str, cookie_index: int = 0, verbose: bool = False):
        self.domain: str = domain
        self.cookie_index: int = cookie_index
        self.verbose: bool = verbose
        self.headers: Dict[str, str] = self._get_headers()
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def __del__(self):
        """关闭 session"""
        self.close()

    def close(self) -> None:
        """关闭 session"""
        if hasattr(self, "session"):
            try:
                self.session.close()
            except Exception as e:
                logger.error(f"{LogEmoji.ERROR} 关闭 session 时发生错误: {e}")

    def __enter__(self):
        """进入上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文管理器"""
        self.close()
        return False

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "origin": f"https://{self.domain}",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36",
        }

    def _log(self, level: str, emoji: str, message: str, force: bool = False) -> None:
        """统一日志输出方法"""

        log_message = f"{LogEmoji.COOKIE}[{self.cookie_index}] {LogEmoji.DOMAIN}[{self.domain}] {emoji} {message}"

        if force or self.verbose:
            if level == "info":
                logger.info(log_message)
            elif level == "warning":
                logger.warning(log_message)
            elif level == "error":
                logger.error(log_message)

    def _get_full_url(self, path: str) -> str:
        """获取完整 URL"""
        return f"https://{self.domain}{path}"

    def _make_request(self, url: str, method: str, data: Optional[Dict] = None, cookies: str = "") -> Optional[requests.Response]:
        """发送 HTTP 请求"""
        session_headers = self.headers.copy()
        session_headers["cookie"] = cookies

        try:
            if method.upper() == "POST":
                response = self.session.post(url, headers=session_headers, data=data, timeout=(60, 120))
            elif method.upper() == "GET":
                response = self.session.get(url, headers=session_headers, timeout=(60, 120))
            else:
                self._log("error", LogEmoji.ERROR, f"不支持的 HTTP 方法: {method}", force=True)
                return None

            if not response.ok:
                self._log("warning", LogEmoji.WARNING, f"向 {url} 发起的请求失败，状态码 {response.status_code}。响应内容: {response.text}", force=True)
                return None
            return response
        except requests.exceptions.RequestException as e:
            self._log("error", LogEmoji.ERROR, f"向 {url} 发起请求时发生网络错误: {e}", force=True)
            return None

    def _get_checkin_data(self) -> Dict[str, str]:
        """获取签到数据"""
        return {"token": self.domain}

    @log_method
    def checkin(self, cookies: str) -> Dict[str, Union[str, CheckinStatus]]:
        """执行签到"""
        url = self._get_full_url(self.CHECKIN_URL)
        checkin_data = self._get_checkin_data()
        response = self._make_request(url, "POST", checkin_data, cookies)

        result = {
            "status": "签到失败",
            "points": "0",
            "message": "",
            "code": CheckinStatus.FAILURE,
        }

        if response:
            data = response.json()
            code = data.get("code", -2)
            message = data.get("message", "无消息字段")
            points = str(data.get("points", 0))

            if code == CheckinStatus.SUCCESS.value:
                self._log("info", LogEmoji.SUCCESS, f"{{ code : {code}, points : {points}, message : {message} }}")
                result["code"] = CheckinStatus.SUCCESS
                result["status"] = "签到成功"
                result["points"] = points
                result["message"] = message
            elif code == CheckinStatus.REPEAT.value:
                self._log("info", LogEmoji.REPEAT, f"{{ code : {code}, message : {message} }}", force=True)
                result["code"] = CheckinStatus.REPEAT
                result["status"] = "重复签到"
                result["points"] = "0"
                result["message"] = message
            else:
                self._log("info", LogEmoji.FAIL, f"{{ code : {code}, message : {message} }}", force=True)
                result["code"] = CheckinStatus.FAILURE
                result["status"] = "签到失败"
                result["points"] = "0"
                result["message"] = message
        else:
            self._log("warning", LogEmoji.WARNING, "签到失败", force=True)
            result["code"] = CheckinStatus.FAILURE
            result["status"] = "签到失败"
            result["message"] = "网络请求失败"

        return result

    @log_method
    def get_status(self, cookies: str) -> Tuple[str, int]:
        """获取状态"""

        url = self._get_full_url(self.STATUS_URL)
        response = self._make_request(url, "GET", cookies=cookies)

        if response:
            data = response.json()
            code = data.get("code", -2)
            left_days = data.get("data", {}).get("leftDays", None)

            if left_days is not None:
                left_days_int = int(float(left_days))
                self._log("info", LogEmoji.SUCCESS, f"{{ code : {code}, leftDays : {left_days_int} 天}}")
                return f"{left_days_int} 天", code
            else:
                self._log("info", LogEmoji.FAIL, f"{{ code : {code}, leftDays : {left_days} 天}}", force=True)
                return "None 天", code
        else:
            self._log("warning", LogEmoji.WARNING, "获取状态失败", force=True)
            return "None 天", -2

    @log_method
    def get_points(self, cookies: str) -> Tuple[str, int]:
        """获取积分"""
        url = self._get_full_url(self.POINTS_URL)
        response = self._make_request(url, "GET", cookies=cookies)

        if response:
            data = response.json()
            code = data.get("code", -2)
            points = data.get("points", None)

            if points is not None:
                points_int = int(float(points))
                self._log("info", LogEmoji.SUCCESS, f"{{ code : {code}, points : {points_int} 积分}}")
                points_str = f"{points_int} 积分"
                points_num = points_int
                return points_str, points_num
            else:
                self._log("info", LogEmoji.FAIL, f"{{ code : {code}, points : {points} 积分}}", force=True)
                return "None 积分", 0
        else:
            self._log("warning", LogEmoji.WARNING, "获取积分失败", force=True)
            return "None 积分", 0

    # 注意：自动兑换已删除。积分只查询、不兑换，如需兑换请手动在官网操作。
    # 这里刻意不保留 exchange()，防止旧代码或误调用再次触发兑换。


@dataclass()
class CheckinResult:
    """签到结果"""

    cookie_index: int
    domain: str
    status: str = "签到失败"
    points: str = "0"
    days: str = "None"
    points_total: str = "None"
    exchange: str = "未兑换"
    code: CheckinStatus = CheckinStatus.FAILURE  # 0: 成功, 1: 重复, -2: 失败

    def to_dict(self) -> Dict[str, Union[str, CheckinStatus]]:
        result_dict = asdict(self)
        return result_dict


class PushService:
    """推送服务"""

    def __init__(self, config: Config):
        self.config = config

    def send(self, title: str, content: str) -> bool:
        """发送推送"""
        if not self.config.push_key:
            logger.info(f"{LogEmoji.WARNING} 未设置推送密钥，跳过推送通知。")
            return False

        try:
            pushdeer = PushDeer(pushkey=self.config.push_key)
            pushdeer.send_text(title, desp=content)
            logger.info(f"{LogEmoji.SUCCESS} 推送通知发送成功。")
            return True
        except Exception as e:
            logger.error(f"{LogEmoji.ERROR} 发送推送通知失败: {e}")
            return False


class Checker:
    """签到"""

    def __init__(self, config: Config):
        self.config = config
        self.results = []

    def _log(self, cookie_idx: int, domain: str, emoji: str, message: str, force: bool = False) -> None:
        """统一日志输出方法"""

        if self.config.verbose or force:
            logger.info(f"{LogEmoji.COOKIE}[{cookie_idx}] {LogEmoji.DOMAIN}[{domain}] {emoji} {message}")

    def checkin_all(self):
        """执行所有签到任务：每个 Cookie 只在第一个 status 成功的域名上签到一次。
        这样 glados.cloud 的 Cookie 不会在 railgun.info 上重复签到，
        railgun.info 的 Cookie 也能在备用域名上签到；所有域名 status 都
        返回无权限时，直接判定该 Cookie 已失效，不再盲目签到。"""
        cookie_count = len(self.config.cookies_list)
        logger.info(f"{LogEmoji.INFO} 共 {cookie_count} 个 Cookie，逐个探测可用域名后签到")

        for cookie_idx, cookie in enumerate(self.config.cookies_list, 1):
            logger.info(f"{LogEmoji.START} ========== 开始处理 Cookie {cookie_idx} ==========")
            domain = self._pick_domain(cookie, cookie_idx)
            if domain is None:
                result = CheckinResult(cookie_idx, self.config.DOMAINS[0],
                                       status="签到失败", code=CheckinStatus.FAILURE,
                                       days="None 天", points_total="None 积分",
                                       exchange="未兑换")
                self.results.append(result)
                logger.error(f"{LogEmoji.COOKIE}[{cookie_idx}] {LogEmoji.ERROR} Cookie 已失效或无权限："
                             f"glados.cloud / glados.rocks / railgun.info 的 status 均返回无权限，"
                             f"请重新登录 GLaDOS 抓取最新 Cookie 更新 GLADOS_COOKIES / GLADOS_COOKIES_2。")
                continue

            result = self._checkin_on_domain(cookie, cookie_idx, domain)
            self.results.append(result)
            result_message = f"结果: {result.status}"
            if result.code == CheckinStatus.SUCCESS:
                if self.config.verbose:
                    result_message = f"结果: {result.status}, 获得 {result.points} 积分, 剩余 {result.days}, 总 {result.points_total}, {result.exchange}"
                self._log(cookie_idx, domain, LogEmoji.SUCCESS, result_message, force=True)
            else:
                self._log(cookie_idx, domain, LogEmoji.WARNING, result_message, force=True)

    def _pick_domain(self, cookie: str, cookie_idx: int) -> Optional[str]:
        """探测哪个域名认这个 Cookie：status 返回剩余天数即为可用。"""
        for domain in self.config.DOMAINS:
            with API(domain, cookie_idx, verbose=self.config.verbose) as api:
                days_str, status_code = api.get_status(cookie)
            if status_code == 0 and days_str != "None 天":
                logger.info(f"{LogEmoji.COOKIE}[{cookie_idx}] {LogEmoji.DOMAIN}[{domain}] "
                            f"{LogEmoji.SUCCESS} 该域名认此 Cookie，剩余 {days_str}")
                return domain
            logger.info(f"{LogEmoji.COOKIE}[{cookie_idx}] {LogEmoji.DOMAIN}[{domain}] "
                        f"status 未通过（code={status_code}），试下一个域名")
        return None

    def _checkin_on_domain(self, cookie: str, cookie_idx: int, domain: str) -> CheckinResult:
        result = CheckinResult(cookie_idx, domain)
        result.exchange = "未兑换（自动兑换已关闭）"

        with API(domain, cookie_idx, verbose=self.config.verbose) as api:
            # 1. 获取状态（_pick_domain 已确认可用，这里只为记录剩余天数）
            self._log(cookie_idx, domain, LogEmoji.STATUS, "查询剩余天数")
            days_str, status_code = api.get_status(cookie)
            result.days = days_str

            # 2. 签到：网络失败或 Cloudflare 验证失败（code 5，11-14 两个账号
            # 都是这个错）时重试，间隔 60 秒、最多重试 2 次；Cookie 失效不重试。
            # Cloudflare 拦截是偶发的，GitHub 机房 IP 容易被拦，重试和第二天
            # 的第二次签到都是兜底。
            self._log(cookie_idx, domain, LogEmoji.CHECKIN, "执行签到")
            checkin_result = api.checkin(cookie)
            for attempt in (1, 2):
                message = checkin_result.get("message", "")
                retryable = checkin_result.get("code") == CheckinStatus.FAILURE and (
                    "网络请求失败" in message or "Cloudflare" in message
                )
                if not retryable:
                    break
                logger.warning(f"{LogEmoji.COOKIE}[{cookie_idx}] 签到失败可重试（{message}），60 秒后第 {attempt} 次重试")
                time.sleep(60)
                checkin_result = api.checkin(cookie)
            result.status = checkin_result["status"]
            result.code = checkin_result.get("code", CheckinStatus.FAILURE)
            result.points = checkin_result.get("points", "0")

            # 3. 获取积分（只查询，不兑换）
            self._log(cookie_idx, domain, LogEmoji.POINTS, "查询总积分")
            points_str, points_num = api.get_points(cookie)
            result.points_total = points_str

            # 4. 不执行兑换：积分只累积，兑换请手动在官网操作。

        return result

    def get_results(self) -> List[Dict[str, str]]:
        """获取所有结果"""
        return [result.to_dict() for result in self.results]

    def format_results(self) -> Tuple[str, str, str]:
        """格式化结果"""
        results = self.get_results()

        success_count = sum(1 for r in results if r["code"] == CheckinStatus.SUCCESS)
        repeat_count = sum(1 for r in results if r["code"] == CheckinStatus.REPEAT)
        fail_count = sum(1 for r in results if r["code"] == CheckinStatus.FAILURE)

        title = f"GLaDOS 签到, 成功{success_count}, 失败{fail_count}, 重复{repeat_count}"

        send_content_lines = []
        log_content_lines = []
        for i, res in enumerate(results, 1):
            line = f"#{i} P:{res['points']} 剩余:{res['days']} 总积分:{res['points_total']} | {res['status']} | {res['exchange']}"
            send_content_lines.append(line)

            if self.config.verbose:
                log_line = line
            else:
                log_line = f"#{i} {res['status']}"
            log_content_lines.append(log_line)

        content = "\n".join(send_content_lines)
        log_content = "\n".join(log_content_lines)
        return title, content, log_content


# 初始化日志
logger = init_logger()


def main():
    """主函数：签到失败时以非零退出码结束，确保 Actions 显示失败。"""
    failed = False
    title = "# 未执行签到"
    content = ""
    config = None

    try:
        logger.info(f"{LogEmoji.START} 步骤 1: 加载配置")
        config = Config()

        if not config.cookies_list:
            logger.error(f"{LogEmoji.ERROR} 未找到有效的 Cookie，退出程序。")
            title = "# 未找到 cookies!"
            failed = True
        else:
            logger.info(f"{LogEmoji.START} 步骤 2: 执行签到")
            checker = Checker(config)
            checker.checkin_all()

            logger.info(f"{LogEmoji.START} 步骤 3: 格式化结果")
            title, content, log_content = checker.format_results()
            logger.info(f"\n{LogEmoji.END}========== 签到总结 ==========\n{title}\n{log_content}")

            # 重复签到属于可接受结果；任何实际失败都应使 CI 失败。
            failed = not checker.results or any(
                result.code not in (CheckinStatus.SUCCESS, CheckinStatus.REPEAT)
                for result in checker.results
            )
    except Exception:
        # 不输出 Cookie 等敏感环境变量。
        logger.exception(f"{LogEmoji.ERROR} 主程序执行过程中发生未预期的错误")
        title = "# 脚本执行出错"
        content = "请查看 GitHub Actions 日志并核对登录凭据。"
        failed = True

    logger.info(f"{LogEmoji.START} 步骤 4: 发送推送")
    if config is not None:
        try:
            PushService(config).send(title, content)
        except Exception:
            logger.exception(f"{LogEmoji.ERROR} 推送出现异常")
    logger.info(f"{LogEmoji.END} 签到完成")

    if failed:
        logger.error("签到任务失败：请检查失败账号对应的 GLADOS_COOKIES / GLADOS_COOKIES_2 并核对认证流程。")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
