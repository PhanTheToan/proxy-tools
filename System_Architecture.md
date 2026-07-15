# Tài liệu Thiết kế Kiến trúc Hệ thống: Local Reverse Proxy Manager (LRPM)
*(Cập nhật theo thực tế triển khai - Python + Node.js)*

## 1. Tổng quan Dự án (Project Overview)
Công cụ Local Reverse Proxy Manager (LRPM) là một ứng dụng chạy ở môi trường máy tính cá nhân (localhost), đóng vai trò như một Gateway trung gian kết hợp khả năng tự động phân tích (Auto-discovery).
Hệ thống cho phép khởi tạo, quản lý và tổ chức các proxy server cục bộ theo cấu trúc phân cấp (cây thư mục đa cấp giống CMS). Công cụ cung cấp một UI/UX chuyên nghiệp, giúp nhà phát triển dễ dàng mapping các cổng local tới target sites và quản lý hàng loạt API/Subdomain tự động sinh ra.

## 2. Kiến trúc Công nghệ Hiện tại (Current Tech Stack)

Hệ thống được thiết kế theo mô hình Micro-process (tiến trình con), tách biệt hoàn toàn giữa Control Plane và Data Plane.

### 2.1 Control Plane (Lõi Quản trị API & Process) - `Python 3`
- **Tập tin chính:** `backend/server.py`
- **Công nghệ:** Python 3 (`http.server` tiêu chuẩn, không dùng framework nặng nề).
- **Nhiệm vụ:**
  - Cung cấp RESTful API để Frontend quản lý dữ liệu.
  - Tương tác với SQLite Database (`mappings.db`).
  - Quản lý vòng đời tiến trình (Process Lifecycle Management): Gọi lệnh `subprocess.Popen` để tự động spawn (bật), lưu trữ PID, và kill (tắt) các tiến trình proxy Node.js.
  - Phục vụ (Serve) các file tĩnh cho Frontend (HTML, CSS, JS).

### 2.2 Data Plane (Lõi Proxy Chuyển tiếp) - `Node.js`
- **Tập tin chính:** `proxy.js`
- **Công nghệ:** Node.js kết hợp thư viện `http-proxy` và `stream-replace`.
- **Lý do lựa chọn:** Node.js xử lý stream cực kỳ xuất sắc, cho phép can thiệp (intercept) và sửa đổi (rewrite) trực tiếp nội dung Body (HTML) và Headers (Cookie, Location) on-the-fly mà không tốn bộ nhớ đệm.
- **Nhiệm vụ:**
  - Lắng nghe trên cổng local được chỉ định.
  - Xử lý CORS và thay đổi `Host` header.
  - Tự động thay thế/viết lại các liên kết URL (Rewrite URLs) bên trong HTML trả về.
  - Inject mã JavaScript tự động nhận diện URL (Auto-discovery injection) vào thẻ `<head>` của trang web đích.

### 2.3 Cơ sở dữ liệu (Database) - `SQLite`
- Khởi tạo tự động tại `backend/mappings.db`. Lưu trữ toàn bộ trạng thái hệ thống. Hỗ trợ cấu trúc đa cấp (Parent - Child).

### 2.4 Frontend (Giao diện Người dùng) - `Vanilla JS`
- **Công nghệ:** HTML5, CSS3 tinh thuần, Vanilla JavaScript (`app.js`).
- Chú trọng tối đa vào tốc độ phản hồi và UI/UX Pro Max (Dual-theme Light/Dark, Drag & Drop, CSS Grid CMS Layout).

---

## 3. Kiến trúc Luồng Dữ liệu (Workflow & Architecture)

### 3.1 Luồng Tự động nhận diện URL (Auto-Discovery Flow) - Tính năng cốt lõi
1. **Client Request:** Browser truy cập `http://localhost:<port>`.
2. **Intercept & Inject:** Node.js `proxy.js` chặn gói tin HTML trả về từ Server đích, chèn đoạn mã `<script>` thu thập URL.
3. **Data Collection:** Khi trang HTML load trên browser, đoạn script quét toàn bộ `<a>`, `<img>`, `<script>`... và gửi một POST request ẩn về `http://localhost:8085/api/v1/mappings/auto-discover`.
4. **Auto-Categorization:** Backend Python nhận danh sách URL. 
   - Tự động phân loại URL thành: `Subdomains`, `Social & CDN`, `External`...
   - Tự động tạo Folder tương ứng nếu chưa có.
   - Tự động cấp phát cổng (port) ngẫu nhiên cho các URL mới và gán vào Folder.
   - Gọi Node.js khởi động ngay lập tức các cổng mới.

### 3.2 Luồng Quản trị Giao diện (UI Control Flow)
- Giao diện tải danh sách dưới dạng Node Tree thông qua thuật toán phân tích đệ quy (Recursive Tree Build).
- Kéo thả (Drag & Drop) một phần tử sẽ kích hoạt luồng `PUT /move`, cập nhật `parent_id` trong DB và re-render cấu trúc DOM.

---

## 4. Thiết kế Cơ sở dữ liệu (Database Schema)

Bảng `mappings` được thiết kế lại để hỗ trợ tính năng Thư mục và quản lý cây đa cấp:

| Field Name | Type | Constraints | Description |
|---|---|---|---|
| `id` | VARCHAR | Primary Key | ID sinh tự động (uuid4) |
| `local_port` | INTEGER | Nullable | Cổng localhost (Null nếu là Folder) |
| `target_url` | VARCHAR | Nullable | URL đích (Null nếu là Folder) |
| `is_active` | BOOLEAN | Default True | Trạng thái proxy (Đang bật/Đã tắt) |
| `description`| TEXT | Nullable | Tên thư mục hoặc nhãn ghi chú |
| `created_at` | DATETIME| Default Now() | Thời gian khởi tạo |
| `parent_id` | VARCHAR | Nullable | Trỏ tới `id` của thư mục cha (Root nếu Null) |
| `item_type` | VARCHAR | Default 'proxy' | Phân loại: `proxy` hoặc `folder` |

---

## 5. Danh sách API Endpoints

### 5.1 Proxy Management
- `GET /api/v1/mappings`: Trả về toàn bộ Node.
- `POST /api/v1/mappings`: Thêm proxy thủ công hoặc thêm Folder.
- `PUT /api/v1/mappings/:id`: Sửa thông tin.
- `DELETE /api/v1/mappings/:id`: Xóa (Hỗ trợ **Cascade Delete** - xóa luôn toàn bộ proxy con nếu đây là Folder).
- `POST /api/v1/mappings/:id/toggle`: Đóng/Mở cổng.

### 5.2 Folder & Advanced Operations
- `DELETE /api/v1/folders/:id/empty`: Xóa trống thư mục (Chỉ xóa các URL con, giữ lại cấu trúc vỏ thư mục).
- `PUT /api/v1/mappings/:id/move`: Thay đổi `parent_id` (Di chuyển Proxy/Folder).
- `POST /api/v1/mappings/auto-discover`: Nhận batch URLs từ injected JS để tự động tạo proxy.
