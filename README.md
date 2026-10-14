# 🌿 PIPO GARDEN - HỆ THỐNG GỌI MÓN MÃ QR & TỰ ĐỘNG IN PHIẾU BẾP (KOT)

Hệ thống quản lý nhà hàng thông minh chuyên biệt cho **PiPo Garden**:
- **Khách hàng**: Quét mã QR riêng tại bàn bằng điện thoại (Camera/Zalo) để xem menu, chọn món, ghi chú và gửi đơn.
- **Nhà bếp (Kitchen)**: Tự động in phiếu làm món (Kitchen Order Ticket - KOT) khổ 80mm có còi hú & đèn cảnh báo ngay trong 0.2 giây mà không cần nhân viên ghi order tại bàn. Đồng thời hiển thị trên màn hình điều phối KDS.
- **Thu ngân (POS)**: Quản lý sơ đồ bàn, duyệt gọi món, theo dõi trạng thái món ăn, xuất mã QR bàn và thanh toán VietQR động.

---

## 📁 Cấu Trúc Hệ Thống

```text
d:\AI\Restaurant\
├── app/
│   ├── database.py             # SQLite DB: Bàn, Session, Menu, Orders, PrintJobs
│   ├── escpos.py               # Bộ tạo mã byte ESC/POS & định dạng phiếu in bếp 80mm
│   ├── main.py                 # FastAPI Application & WebSockets Hub
│   ├── routers/
│   │   ├── tables.py           # API Bàn ăn & tạo ảnh mã QR
│   │   ├── menu.py             # API Thực đơn & Tùy chọn món (Modifiers)
│   │   ├── orders.py           # API Đặt món, tách trạm & điều phối in tự động
│   │   └── pos.py              # API Thu ngân, thanh toán & VietQR
│   └── templates/
│       ├── customer.html       # Web App gọi món trên điện thoại cho khách
│       ├── kds.html            # Màn hình điều phối chế biến nhà bếp (KDS)
│       ├── pos.html            # Bảng điều khiển thu ngân & In thẻ QR để bàn
│       └── printer_monitor.html# Mô phỏng máy in nhiệt 80mm ảo (Simulator)
├── print_agent/
│   ├── agent.py                # Local Print Agent chạy ngầm trên máy tính thu ngân
│   └── config.json             # Cấu hình IP máy in LAN hoặc USB
├── run_server.py               # Khởi chạy Backend Server
├── run_agent.py                # Khởi chạy Print Agent
├── start_pipo_garden.bat       # 1-Click khởi động toàn bộ hệ thống cho Windows
└── pipo_garden.db              # Cơ sở dữ liệu SQLite tự khởi tạo kèm menu mẫu
```

---

## 🚀 Hướng Dẫn Khởi Động Nhanh (1-Click)

### Cách 1: Chạy file `.bat` tiện lợi (Dành cho máy tính thu ngân)
Nhấp đúp chuột vào file:
👉 **`start_pipo_garden.bat`**

Hệ thống sẽ tự động bật máy chủ, kết nối Print Agent và mở ngay trang Quản trị Thu ngân trên trình duyệt.

---

### Cách 2: Khởi chạy thủ công bằng dòng lệnh

**Bước 1: Khởi động Server**
```powershell
python run_server.py
```
Máy chủ sẽ lắng nghe tại cổng `8000`.

**Bước 2: Khởi động Print Agent (In phiếu bếp tự động)**
Mở thêm một cửa sổ terminal mới và chạy:
```powershell
python run_agent.py
```

---

## 🌐 Các Đường Dẫn Truy Cập Hệ Thống

| Giao diện | Địa chỉ URL | Vai trò truy cập & Mục đích sử dụng |
| :--- | :--- | :--- |
| **Trang Chủ & Cổng Đăng Nhập** | `http://localhost:8000/` | Trang chủ PiPo Garden, phân quyền đăng nhập tự động chuyển hướng theo vai trò |
| **Quản Trị POS & Thu Ngân** | `http://localhost:8000/pos` | **Quản trị viên & Thu ngân**: Sơ đồ bàn, VietQR động, Báo cáo doanh thu, Quản trị nhân viên, Liên kết Kho |
| **Không Gian Bếp (Kitchen Hub)** | `http://localhost:8000/kitchen` | **Bếp trưởng**: KDS vé đơn, Bật/Tắt món hết hàng, Định lượng nguyên vật liệu (BOM) & tính Food Cost |
| **Nhân Viên Phục Vụ (Waiter)** | `http://localhost:8000/waiter` | **Nhân viên khác / Phục vụ**: Xem danh sách bàn đang có món gì, trạng thái nấu/chờ bưng, xử lý gọi phục vụ |
| **Quản Lý Kho & Nhập NVL** | `http://localhost:8000/inventory` | **Thủ kho / Quản lý**: Danh mục nguyên vật liệu, Nhập kho (Goods Receipt), Cảnh báo tồn thấp, Sổ nhật ký trừ kho tự động |
| **Máy In Bếp Ảo (Simulator)** | `http://localhost:8000/printer-monitor` | Giả lập xem phiếu in nhiệt 80mm đùn ra khi khách đặt món (kèm còi hú) |
| **Khách Gọi Món Tại Bàn** | `http://localhost:8000/table/<qr_token>` | Khách quét QR là mở trang này trên điện thoại (gọi món, theo dõi trạng thái, gọi phục vụ) |

---

## 👥 Phân Nhóm Tài Khoản & Tự Động Chuyển Hướng (Role Redirection)

Khi đăng nhập tại **`http://localhost:8000/`**, hệ thống sẽ tự động đưa người dùng vào đúng không gian làm việc tương ứng:

| Nhóm tài khoản | Tên đăng nhập | Mật khẩu | Trang chuyển hướng tự động | Chức năng chính |
| :--- | :--- | :--- | :--- | :--- |
| **Quản trị viên (ADMIN)** | `admin` | `admin123` | `http://localhost:8000/pos` | Toàn quyền hệ thống: Báo cáo tài chính, quản lý nhân viên, giám sát kho |
| **Thu ngân (CASHIER)** | `thungan` | `123456` | `http://localhost:8000/pos` | Mở bàn, chốt hóa đơn, tạo mã VietQR động, in phiếu thanh toán |
| **Bếp (CHEF)** | `bep` | `123456` | `http://localhost:8000/kitchen` | Màn hình KDS, bật/tắt còn món/hết món, cài đặt công thức định lượng (BOM) |
| **Nhân viên khác (WAITER)**| `phucvu` | `123456` | `http://localhost:8000/waiter` | Theo dõi các bàn đang có những món gì, xác nhận đã bưng món, chuông gọi phục vụ |

---

## 🍳 Không Gian Bếp & Định Lượng Món Ăn (Recipe BOM)
- Truy cập tại: `http://localhost:8000/kitchen`
- **Tab 1: Màn hình KDS**: Hiển thị đơn theo bàn, bộ đếm thời gian thực, nút chuyển trạng thái món: *Bắt đầu nấu $\rightarrow$ Đã nấu xong $\rightarrow$ Đã bưng ra bàn*. Có chuông âm thanh Ting Ting khi đơn mới tới.
- **Tab 2: Quản trị món & Thực đơn**: Xem toàn bộ danh mục món ăn, giá bán, trạm chế biến và nút gạt Bật/Tắt còn hàng ngay tức thì.
- **Tab 3: Định lượng nguyên vật liệu (BOM)**: Thiết lập công thức từng món ăn (ví dụ: 1 phần *Bò Fuji Nướng Đá* tốn 0.25kg Thịt Bò + 0.05 lít Sốt Tiêu Đen BBQ). Tự động tính toán Food Cost và tỷ suất lợi nhuận tức thời.

---

## 📦 Quản Lý Kho & Tự Động Khấu Trừ Tồn Kho
- Truy cập tại: `http://localhost:8000/inventory`
- **Liên kết toàn hệ thống**:
  1. Khi Bếp bấm **"Bắt đầu nấu"** (hoặc **"Đã nấu xong"**), hệ thống tự động tra cứu công thức BOM của món đó và tự động trừ số lượng nguyên vật liệu tương ứng trong kho.
  2. Cơ chế **Idempotent (`inventory_deducted`)** đảm bảo nguyên vật liệu chỉ bị trừ đúng 1 lần duy nhất cho mỗi món trên đơn, không bao giờ bị trừ trùng lặp.
  3. Giao dịch khấu trừ được ghi nhận minh bạch vào bảng nhật ký biến động kho với loại giao dịch `ORDER_DEDUCT` ghi rõ mã đơn và tên bàn.
- **Tính năng nhập kho**: Thủ kho có thể nhập thêm nguyên vật liệu kèm đơn giá nhập, nhà cung cấp và ghi chú hóa đơn.
- **Cảnh báo mức tồn an toàn**: Tự động cảnh báo màu đỏ/cam khi nguyên vật liệu đạt mức dưới tồn kho tối thiểu.

---

## 📊 Module Báo Cáo Doanh Thu (Ngày / Tháng / Năm)
Hệ thống cung cấp 2 chế độ báo cáo chuyên sâu tại tab **"Báo cáo doanh thu"** trên trang Quản trị (`/pos`):
1. **Báo cáo tổng quan (Overview)**:
   - Các chỉ số KPI: Doanh thu hôm nay, Doanh thu tháng này, Doanh thu năm nay, AOV.
   - Biểu đồ xu hướng 7 ngày (Line Chart) và 12 tháng (Bar Chart).
   - Biểu đồ cơ cấu doanh thu theo khu vực bàn (Sân Vườn, VIP, Tầng Lửng).
   - Bảng xếp hạng Top 5 món ăn & đồ uống bán chạy nhất.
2. **Báo cáo chi tiết (Detailed Audit)**:
   - Lọc linh hoạt theo: **Từng Ngày**, **Từng Tháng**, hoặc **Cả Năm**.
   - Bảng kê chi tiết từng hóa đơn, mã đơn, thời gian, tên bàn, món gọi, hình thức thanh toán (VietQR/Tiền mặt), tổng tiền.
   - Hỗ trợ nút **"In Báo Cáo Này"** chuẩn in ấn.

*(Ví dụ trải nghiệm thử bàn 1: `http://localhost:8000/pos` $\rightarrow$ bấm vào Bàn Vườn 01 $\rightarrow$ bấm "Xem giao diện gọi món của bàn này".)*

---

## 🖨️ Hướng Dẫn Cấu Hình Máy In Bếp Vật Lý (Xprinter XP-C300H / Epson)

1. Cắm dây mạng LAN từ Router của quán vào máy in bếp.
2. In phiếu test trên máy in (giữ nút FEED khi bật nguồn) để lấy địa chỉ IP của máy (Ví dụ: `192.168.1.201`).
3. Mở file `print_agent/config.json` và cấu hình:
```json
{
  "server_ws_url": "ws://127.0.0.1:8000/ws/printer",
  "simulate_mode": true,
  "printers": {
    "HOT_KITCHEN": {
      "name": "Máy in Bếp Nóng (Xprinter XP-C300H)",
      "type": "tcp",
      "host": "192.168.1.201",
      "port": 9100,
      "enabled": true
    },
    "BAR": {
      "name": "Máy in Quầy Bar",
      "type": "tcp",
      "host": "192.168.1.202",
      "port": 9100,
      "enabled": false
    }
  }
}
```
4. Đổi `"enabled": true` cho máy in bạn muốn xuất lệnh in thật. Khi có đơn mới, Print Agent sẽ vừa in ra máy in thật qua cổng 9100, vừa hiển thị trên màn hình máy in ảo.

---

---

## 🔒 Cơ Chế Bảo Mật & Chống Truy Cập Trực Tiếp (Multi-Layer Security)

Hệ thống được trang bị cơ chế bảo mật nghiêm ngặt 2 lớp (**Server-Side** & **Client-Side**) nhằm ngăn chặn hoàn toàn việc người dùng tự ý gõ link để vào các trang quản trị bên trong:

### 1. Khóa Truy Cập Trực Tiếp Qua Đường Dẫn (Direct URL Protection)
- **Tất cả các trang nội bộ** (`/pos`, `/kitchen`, `/waiter`, `/inventory`, `/kds`, `/printer-monitor`) đều được bảo vệ bởi bộ lọc kiểm soát truy cập `check_page_access`:
  - Nếu người dùng **chưa đăng nhập**: Máy chủ lập tức gửi mã phản hồi HTTP `303 See Other` và chuyển hướng thẳng về Trang Chủ: `/?error=unauthorized&redirect=<trang_yeu_cau>`.
  - Trang chủ sẽ bật khung thông báo cảnh báo màu vàng: *"Yêu cầu bảo mật: Vui lòng đăng nhập tài khoản nhân viên!"*.
- **Phân quyền theo nhóm tài khoản (Role-based Guard)**:
  - Nếu nhân viên thuộc nhóm **Phục vụ (`WAITER`)** cố tình gõ link `/pos` hoặc `/inventory`: Hệ thống lập tức chặn lại và đẩy về `/waiter?error=denied`.
  - Nếu tài khoản **Bếp (`CHEF`)** cố tình vào `/pos`: Hệ thống chặn lại và đẩy về `/kitchen?error=denied`.
  - Chỉ có **Quản trị viên (`ADMIN`)** mới có toàn quyền truy cập tất cả các trang.

### 2. Chữ Ký Số Chống Giả Mạo Cookie (HMAC-SHA256 Token)
- Thay vì lưu tên người dùng dạng văn bản thuần, hệ thống tạo **Token phiên đã ký số** bằng thuật toán HMAC-SHA256 với khóa bí mật (`AUTH_SECRET`).
- Cookie `pipo_session` được gán cờ `HttpOnly=True`, `SameSite="lax"` giúp ngăn chặn hoàn toàn các cuộc tấn công đánh cắp cookie qua mã độc JavaScript (XSS).
- Kẻ xấu không thể tự ý sửa cookie để đóng giả tài khoản `admin`.

### 3. Bảo Vệ API Nội Bộ (API Guard)
- Toàn bộ các API nhạy cảm (`/api/reports/*`, `/api/auth/staff/*`, `/api/inventory/*`, `/api/pos/checkout`) đều được bọc bởi `require_api_auth`:
  - Trả về mã lỗi HTTP `401 Unauthorized` nếu gọi API khi chưa đăng nhập.
  - Trả về mã lỗi HTTP `403 Forbidden` nếu người gọi không đủ thẩm quyền (ví dụ: nhân viên bếp cố tình gọi API xóa nhân viên hoặc API báo cáo doanh thu).

### 4. Ngoại Lệ Dành Riêng Cho Khách Tại Bàn
- Trang gọi món qua mã QR (`/table/{qr_token}`) được thiết kế dành riêng cho thực khách. Khách quét mã QR tại bàn sẽ vào thẳng thực đơn gọi món mà **không cần đăng nhập nhân viên**, với mã định danh bàn được mã hóa bảo mật chống giả mạo.
