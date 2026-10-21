# Vietnam Timezone Utilities (Asia/Ho_Chi_Minh, UTC+7)
from datetime import datetime, timezone, timedelta
import os
import time

VN_TZ = timezone(timedelta(hours=7))

# Áp dụng múi giờ cho process trên hệ điều hành Linux / Container
try:
    os.environ["TZ"] = "Asia/Ho_Chi_Minh"
    if hasattr(time, "tzset"):
        time.tzset()
except Exception:
    pass

def now_vn() -> datetime:
    """Trả về datetime hiện tại theo đúng múi giờ chuẩn Việt Nam (UTC+7 / GMT+7)."""
    return datetime.now(VN_TZ)

def now_vn_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Trả về chuỗi ngày giờ hiện tại chuẩn Việt Nam."""
    return datetime.now(VN_TZ).strftime(fmt)

def now_vn_time_str(fmt: str = "%H:%M:%S") -> str:
    """Trả về chuỗi giờ phút giây hiện tại chuẩn Việt Nam (mặc định HH:MM:SS)."""
    return datetime.now(VN_TZ).strftime(fmt)

def now_vn_date_str(fmt: str = "%Y-%m-%d") -> str:
    """Trả về chuỗi ngày hiện tại chuẩn Việt Nam (YYYY-MM-DD)."""
    return datetime.now(VN_TZ).strftime(fmt)
