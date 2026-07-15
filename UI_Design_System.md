# Proxy Manager - UI/UX Design System & Architecture

Tài liệu này tổng hợp toàn bộ triết lý thiết kế, cấu trúc giao diện và các biến CSS của dự án `Proxy Manager`. Mục đích để làm tài liệu tham chiếu (Reference) giúp cho việc refactor, bảo trì hoặc mở rộng giao diện sau này diễn ra nhanh chóng và đồng nhất.

## 1. Triết lý thiết kế (Design Philosophy)
- **UI-UX Pro Max:** Áp dụng triết lý thiết kế của các hệ thống SaaS hiện đại, tập trung vào không gian (whitespace), độ tương phản và các thành phần bo góc viền nhẹ nhàng.
- **Drill-Down Analytics:** Sử dụng Layout dạng CMS (Content Management System) với 2 phân vùng (Hai cột: Cột điều hướng bên trái và cột nội dung chi tiết bên phải).
- **Hỗ trợ 2 Chế độ (Dual Theme):** Hỗ trợ Dark Mode (mặc định - chuẩn OLED) và Light Mode.

## 2. Cấu trúc Layout (Layout Structure)
File `index.html` sử dụng CSS Grid (`.layout-cms`) chia màn hình thành 2 phần tĩnh:
- **Sidebar (Cột trái - 280px):**
  - Chứa Logo và cây thư mục (Tree View).
  - Hỗ trợ Đóng/Mở (Expand/Collapse) đệ quy vô hạn các thư mục con (Sử dụng biểu tượng chevron).
  - Kéo thả (Drag & Drop) các đối tượng vào thư mục.
- **Main Content (Cột phải - 1fr):**
  - Header: Breadcrumbs (Điều hướng Home > Folder), thanh công cụ tìm kiếm, nút thêm mới và Nút chuyển đổi giao diện (Theme Toggle).
  - Bảng dữ liệu (Table Container): Hiển thị dạng phẳng (Flat List) toàn bộ nội dung của thư mục đang chọn (Kéo theo cả URL của các thư mục con bên trong nó). Cấu trúc bảng gọn gàng, không dùng Checkbox truyền thống ở đầu hàng.

## 3. Hệ thống Token màu sắc (Color Tokens)
Sử dụng CSS Variables định nghĩa ở `:root` và `[data-theme="light"]`.

| Biến CSS | Dark Mode (Mặc định) | Light Mode | Ý nghĩa / Ứng dụng |
|---|---|---|---|
| `--color-background` | `#020617` (Đen sâu) | `#F8FAFC` (Trắng xám) | Màu nền tổng thể |
| `--color-secondary` | `#1E293B` (Xám đen) | `#FFFFFF` (Trắng tinh) | Nền của các Box (Sidebar, Bảng, Search) |
| `--color-primary` | `#0F172A` | `#2563EB` | Màu thương hiệu chính |
| `--color-foreground` | `#F8FAFC` (Trắng) | `#0F172A` (Đen) | Màu chữ chính (Tiêu đề, Text) |
| `--color-muted` | `#1A1E2F` | `#F1F5FD` | Nền phụ (Hover row, Header Table) |
| `--color-border` | `#334155` | `#E4ECFC` | Viền ngăn cách (Borders) |
| `--color-accent` | `#22C55E` (Xanh lá) | `#2563EB` (Xanh dương) | Màu nhấn (Nút Primary, Switch) |
| `--color-link` | `#38BDF8` (Cyan) | `#1D4ED8` (Royal Blue) | Màu của các đường link URL |

## 4. Typography (Phông chữ)
- **Font chính:** `Fira Sans`, sans-serif (Sử dụng cho toàn bộ UI, thân thiện và hiện đại).
- **Font code:** `Fira Code`, monospace (Sử dụng cho cột URL để phân biệt và dễ copy).
- **Trọng lượng (Weight):** 
  - Tiêu đề (Header, Logo): `700` (Bold)
  - Table Header (`th`): `600` (Semi-bold), size `0.75rem` (12px), in hoa.
  - URL (`.target-url`): `500` (Medium).

## 5. UI Components (Các thành phần Giao diện)

### a. Bảng dữ liệu (Data Table)
- Lựa chọn hàng (Row Selection): Không dùng checkbox. Người dùng click trực tiếp vào một dòng (`tr`) để bôi đậm dòng đó (Thêm class `.selected`).
- Nút Bulk Action: Nút Delete Selected chỉ hiện khi có ít nhất 1 dòng được chọn (dùng Set() trong JS để quản lý trạng thái).
- Màu Hover: Nền chuyển nhẹ sang `--color-muted`. Màu Active: `#2563EB` với Opacity 0.15.

### b. Status Switch (Nút Bật/Tắt)
- Thiết kế mô phỏng iOS Toggle (`.switch`).
- Khi OFF: Nền xám mờ (`--color-border`). Núm tròn (Slider) nằm bên trái.
- Khi ON: Nền chuyển sang xanh ngọc `#10B981`. Núm di chuyển sang phải (Transform).
- Sử dụng box-shadow kết hợp cubic-bezier tạo cảm giác vật lý.

### c. Tags (Nhãn dán)
- Dành cho "Auto-discovered" hoặc "Group": `.tag-auto`.
- Nền sử dụng mã màu rgba để tạo độ trong suốt 10% kết hợp với chữ màu đậm, giúp tag nổi bật nhưng không lấn át.

### d. Tree View (Cây thư mục)
- Mũi tên đóng mở: Class `.chevron-sidebar`, xoay đệ quy qua biến `transform: rotate(90deg)`.
- Đường kẻ đứt nét: Dùng padding kết hợp `.tree-line` (CSS border-left đứt nét) để tạo hệ thống phân cấp trực quan giống VS Code.

## 6. Lời khuyên Refactor (Refactoring Guidelines)
Nếu cần thêm chức năng hoặc Refactor lại sau này:
1. Giữ nguyên DOM Structure trong `renderApp()`. Các function đã tách bạch: `renderSidebar`, `renderBreadcrumbs`, `renderMainArea`.
2. Hạn chế sử dụng thêm các class màu cứng (Hard-coded colors). Luôn sử dụng biến `--color-...` để không làm vỡ Dual Theme (Light/Dark).
3. Nếu thêm component đè (Modal/Dropdown), lưu ý set `z-index` tương đương `.modal-overlay` (`z-index: 1000`).
