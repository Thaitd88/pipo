# Quy trình phát triển PiPo Garden

> [!IMPORTANT]
> **QUY TẮC BẮT BUỘC TRƯỚC KHI CHỈNH SỬA CODE / DATABASE:**
> Mỗi lần chuẩn bị chỉnh sửa bất kỳ tính năng gì, **PHẢI LUÔN CHẠY ĐỒNG BỘ** từ Host xuống Local trước:
> ```bash
> python scripts/sync_from_host.py
> ```
> 
> **Lý do:** Khách hàng (User) thường xuyên chỉnh sửa giá món, thêm món, đổi hình ảnh và cấu hình trực tiếp trên Host (https://pipogarden.com) trước khi yêu cầu trợ lý AI sửa đổi code. Việc chạy script này đảm bảo:
> 1. Danh sách món ăn và danh mục từ Host được cập nhật 100% vào database local.
> 2. Các mục cấu hình Homepage CMS và System Settings được bảo toàn.
> 3. Không bao giờ bị ghi đè dữ liệu cũ của local lên dữ liệu mới của Host khi deploy.
