# Hướng dẫn Sử dụng: Local Reverse Proxy Manager (LRPM)

## 1. Giới thiệu
**Local Reverse Proxy Manager (LRPM)** là một công cụ mạnh mẽ dành cho việc phân tích mảng Network/Pentest. Khác với các Forward Proxy truyền thống (như Burp Suite hay Charles), công cụ này thiết lập một cụm server "Gateway" tại máy cá nhân (localhost) đóng vai trò đại diện trực tiếp cho các trang web trên internet.

Hệ thống được thiết kế hoàn toàn bằng **Python 3 thuần túy (Zero-dependency)**, nghĩa là bạn không cần cài đặt thêm thư viện (như npm, pip), chỉ cần có Python là chạy được trên mọi hệ điều hành.

---

## 2. Các Tính năng Nổi bật

- **⚡ Giao diện "Premium":** Quản trị bằng Web UI hiện đại với thiết kế Dark Mode & Glassmorphism phản hồi siêu tốc.
- **🔄 Proxy xuyên suốt (Transparent Rewriting):** Hệ thống chặn bắt, tự động giả mạo Header `Host`, tự động thay thế `Location` redirect và cắt bỏ trường `Domain` của các Cookie giúp vượt qua các cơ chế kiểm tra bảo mật phía server một cách mượt mà.
- **🌐 Quét API Nội hàm (Auto-Discovery):** Khi truy cập thông qua Proxy, hệ thống tự động tháo dỡ mã nguồn HTML/JS, quét ra các đường dẫn Subdomain/API đang bị ẩn giấu và tự động mở Port đón đầu chúng.
- **🕵🏻 Thay thế Code trực tiếp (Body Rewriting):** Chèn các proxy local vào thẳng source code của trang mục tiêu, lừa trình duyệt tin rằng nó đang duyệt nội bộ hoàn toàn trên localhost.

---

## 3. Hướng dẫn Khởi chạy

Mở Terminal và làm theo các bước sau:

```bash
# 1. Di chuyển vào thư mục code backend
cd proxy-tools/backend/

# 2. Chạy server bằng Python (không cần cài thêm bất cứ package nào)
python3 server.py
```

Ngay sau khi chạy lệnh, nếu thành công, Terminal sẽ hiển thị:
`LRPM UI running on http://localhost:8085`

Lúc này, công cụ đã sẵn sàng chạy dưới nền hệ điều hành máy bạn.

---

## 4. Hướng dẫn Sử dụng

1. **Truy cập Bảng điều khiển (Dashboard):**
   Mở trình duyệt (Chrome/Safari) và truy cập vào [http://localhost:8085](http://localhost:8085).
   
2. **Thêm Cấu hình Proxy thủ công:**
   - Bấm nút **"+ Add Proxy"** ở góc phải trên.
   - **Local Port:** Nhập cổng bạn muốn (ví dụ: `33121`).
   - **Target URL:** Nhập trang đích (ví dụ: `https://example.com`).
   - **Description:** Nhập mô tả (ví dụ: "Server Chính").
   - Bấm **Create**.

3. **Bắt đầu trải nghiệm (Proxy Test):**
   - Mở một Tab mới, truy cập vào `http://localhost:33121`.
   - Bạn sẽ thấy nội dung của trang web đích được tải về hoàn chỉnh, kể cả những chức năng yêu cầu bảo mật.
   
4. **Trải nghiệm Hệ thống "Site Map" Tự động:**
   - Sau khi bạn lướt trang web bằng địa chỉ `localhost:33121`, quay trở lại Dashboard quản trị (`localhost:8085`).
   - Bạn sẽ bất ngờ thấy hệ thống tự động liệt kê hàng loạt các kết nối ngầm khác (như `api.example.com`, `login.example.com`) đang được gán sẵn cho các cổng mạng trống! Tất cả đều được đánh nhãn **🤖 Auto-discovered**.
   - Điều này đồng nghĩa, hệ thống đã giúp bạn bắt gọn toàn bộ cây thư mục mạng của trang web chỉ qua 1 lần tải trang.

5. **Bật/Tắt (Toggle):** 
   Sử dụng công tắc trượt trên từng dòng của Table để đóng/mở Port ngay lập tức mà không cần phải gỡ hay tạo lại.

---

## 5. Xử lý Lỗi (Troubleshoot)
- **Lỗi 502 Bad Gateway:** Kiểm tra xem `Target URL` bạn điền đã có `http://` hoặc `https://` chưa. Server đích chặn request do SSL/TLS quá nghiêm ngặt.
- **Port đã được sử dụng (Address already in use):** Port bạn cấp pháp cho Proxy đã bị ứng dụng khác (hoặc chính proxy cũ chưa tắt) chiếm dụng. Đơn giản chọn một Port mới hoặc tắt bớt ứng dụng cũ.
