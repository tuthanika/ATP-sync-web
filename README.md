## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=xjxjin/alist-sync&type=Date)](https://star-history.com/#xjxjin/alist-sync&Date)
# Alist-Sync

Dựa trên một Web Giao diện Alist Công cụ đồng bộ hóa lưu trữ，Hỗ trợ quản lý đa nhiệm vụ、Đồng bộ hóa thời gian、Xử lý khác biệt và các chức năng khác。

<div align="center">
  
[![github tag][gitHub-tag-image]][github-url] [![docker pulls][docker-pulls-image]][docker-url] [![docker image size][docker-image-size-image]][docker-url]  
**Nếu nó dễ sử dụng，Xin vui lòngStar！Cảm ơn bạn rất nhiều！**  [GitHub](https://github.com/xjxjin/alist-sync) [Gitee](https://gitee.com/xjxjin/alist-sync) [DockerHub](https://hub.docker.com/r/xjxjin/alist-sync)
---

[gitHub-tag-image]: https://img.shields.io/github/v/tag/xjxjin/alist-sync
[docker-pulls-image]: https://img.shields.io/docker/pulls/xjxjin/alist-sync
[docker-image-size-image]: https://img.shields.io/docker/image-size/xjxjin/alist-sync
[github-url]: https://github.com/xjxjin/alist-sync
[docker-url]: https://hub.docker.com/r/xjxjin/alist-sync
</div>



## Các tính năng chức năng

- 📱 Xinh đẹp Web Giao diện quản lý
- 🔄 Hỗ trợ quản lý đa nhiệm vụ
- ⏰ ủng hộ Cron Nhiệm vụ thời gian
- 📂 Hỗ trợ hai chế độ: đồng bộ hóa dữ liệu và đồng bộ hóa tệp
- 🗑️ Hỗ trợ nhiều Chính sách xử lý khác biệt（dự trữ/Di chuyển đến thùng rác/xóa bỏ）
- 📝 Ghi nhật ký đồng bộ chi tiết
- 🔒 Hỗ trợ xác thực người dùng và quản lý mật khẩu
- 🐳 ủng hộ Docker triển khai
- 🐉 Hỗ trợ các nhiệm vụ thời gian của bảng điều khiển Qinglong





## Bắt đầu nhanh chóng

### Docker triển khai（gợi ý）

1. Tạo thư mục cần thiết：

```bash
mkdir -p /DATA/AppData/alist-sync-web/data 
```

2. Tạo docker-compose.yml：

```bash
version: '3'

services:
  alist-sync-web:
    image: xjxjin/alist-sync:latest
    container_name: alist-sync
    restart: unless-stopped
    ports:
      - "52441:52441"
    volumes:
      - /DATA/AppData/alist-sync/data:/app/data
    environment:
      - TZ=Asia/Shanghai 
```

3. Bắt đầu dịch vụ：

```bash
docker-compose up -d
```

4. truy cập Web giao diện：

http://localhost:52441

Tài khoản đăng nhập mặc định：
- Tên người dùng：admin
- mật khẩu：admin

## Hướng dẫn sử dụng

### 1. Cấu hình cơ bản

Có thể định cấu hình cho lần sử dụng đầu tiên Alist Thông tin kết nối cơ bản：
- Địa chỉ dịch vụ：Alist Địa chỉ truy cập của dịch vụ
- Tên người dùng：Alist Tài khoản quản trị viên
- mật khẩu：Alist 管理员mật khẩu
- Mã thông báo：Alist Mã thông báo

### 2. Đồng bộ hóa cấu hình tác vụ

Hỗ trợ hai chế độ đồng bộ hóa：

#### Chế độ đồng bộ hóa dữ liệu
- Sao lưu dữ liệu của cùng một thư mục giữa mỗi đĩa mạng
- Chọn nguồn và bộ nhớ đích
- Định cấu hình thư mục đồng bộ hóa
- Hỗ trợ thư mục loại trừ
- Hỗ trợ đồng bộ hóa lưu trữ đa mục tiêu
- Tham khảo hình ảnh cuối cùng

#### Chế độ đồng bộ hóa tệp
- Bạn cần điền vào con đường đầy đủ
- Cấu hình thủ công các đường dẫn nguồn và đích
- Hỗ trợ nhiều cặp đường dẫn
- Hỗ trợ thư mục loại trừ
- Tham khảo hình ảnh cuối cùng

#### Chế độ di chuyển tập tin
- Bạn cần điền vào con đường đầy đủ
- Cấu hình thủ công các đường dẫn nguồn và đích
- Hỗ trợ nhiều cặp đường dẫn
- Hỗ trợ thư mục loại trừ
- Ghi chú：Phương thức chuyển động tệp là sao chép vào đường dẫn đích trước，Sau đó, lần tới khi bạn tự động hóa nhiệm vụ，Xác định xem đường dẫn đích đã có tệp không，Nếu nó tồn tại, hãy xóa tệp đường dẫn nguồn


### 3. Chính sách xử lý khác biệt

Cung cấp ba Phương thức điều trị khác biệt：
- Không được xử lý：Giữ các tệp vi sai trong thư mục đích
- Di chuyển đến thùng rác：Di chuyển tệp diff đến thùng rác của lưu trữ mục tiêu(trash)
- xóa bỏ：直接xóa bỏ目标目录中的差异文件
- di chuyển/xóa bỏ Một số nguồn lưu trữ sẽ thất bại. Chào mừng bạn đến gửiIssue，Tôi đã báo cáo Alist tác giả

### 4. Nhiệm vụ thời gian

- ủng hộ Cron Các tác vụ thời gian cấu hình biểu thức
- Xem tương lai 5 Thời gian thực hiện
- Hỗ trợ chức năng thực thi ngay lập tức

### 5. Xem nhật ký

- Hỗ trợ xem nhật ký hiện tại
- Hỗ trợ xem các bản ghi lịch sử
- Nhật ký được tự động cắt theo ngày

## Mô tả tệp cấu hình

Tất cả các tệp cấu hình được lưu trữ trong `data/config` Mục lục：
- `alist_sync_base_config.json`：Cấu hình kết nối cơ bản
- `alist_sync_sync_config.json`：Đồng bộ hóa cấu hình tác vụ
- `alist_sync_users_config.json`：Cấu hình xác thực người dùng

Các tệp nhật ký được lưu trữ trong `data/log` Mục lục：
- `alist_sync.log`：Nhật ký hiện tại
- `alist_sync.log.YYYY-MM-DD`：Nhật ký lịch sử

## Những điều cần lưu ý

1. Vui lòng sửa đổi mật khẩu đăng nhập mặc định lần đầu tiên
2. Bạn nên sao lưu các tệp cấu hình thường xuyên
3. Hãy chắc chắn Alist Dịch vụ thường có thể truy cập được
4. Nên kiểm tra kết nối trước khi lưu cấu hình
5. Bạn có thể xem thực thi đồng bộ thông qua nhật ký

## Được sử dụng bởi Thanh Đổ

<details>
    <summary>Bấm vào đây để mở rộng/Gấp nội dung</summary>

### tham số

```bash
BASE_URL: Máy chủ cơ bảnURL(Không có kết thúc/)
USERNAME: Tên người dùng
PASSWORD: mật khẩu
TOKEN: Mã thông báo
DIR_PAIRS: Ghép đôi thư mục nguồn và thư mục đích(Ghép đôi thư mục nguồn và thư mục đích，Tách biệt với dấu chấm phẩy，Tách đại tràng)
CRON_SCHEDULE: Ngày lập lịch，Tham khảocronngữ pháp   "điểm giờ ngày mặt trăng tuần" Không yêu cầu，Đừng điền vào như một lịch trình
--Các tham số sau được sử dụng trong thư mục đích:，Nhưng thư mục nguồn không tồn tại trong xử lý tệp，Tham số tùy chọn--
SYNC_DELETE_ACTION: Hành động xóa đồng bộ，Giá trị tùy chọn làmove,delete。
khiSYNC_DELETE_ACTIONĐặt nhưmovegiờ，Tệp sẽ được chuyển sangtrashTrong thư mục；Ví dụ, thư mục bộ nhớ là /dav/quark，Sau đó các tệp dư thừa trong thư mục nguồn sẽ được chuyển sang/dav/quark/trash Trong thư mục
EXCLUDE_DIRS: Loại trừ thư mục
MOVE_FILE: Có di chuyển tệp không，Thư mục nguồn sẽ bị xóa，Và vớiSYNC_DELETE_ACTION Không thể có hiệu lực cùng một lúc
REGEX_PATTERNS: biểu thức chính quy được sử dụng để khớp với tên tệp

```

Thực thi trong nước

```bash
ql raw https://gitee.com/xjxjin/alist-sync/raw/main/alist-sync-ql.py
```
Thực thi quốc tế

```bash
ql raw https://github.com/xjxjin/alist-sync/raw/main/alist-sync-ql.py
```

</details>

## Cập nhật hồ sơ
### v1.1.5
- 2025-03-15
- Đã sửa lỗi báo cáo lỗi cho các biểu thức chính quy khi chúng trống

### v1.1.4
- 2025-02-21
- Đã sửa lỗi báo cáo lỗi cho các biểu thức chính quy khi chúng trống

### v1.1.3
- 2025-02-18
- Đã thêm chức năng biểu thức chính quy
- Hiển thị số phiên bản được tối ưu hóa

### v1.1.2
- 2025-02-08
- Tối ưu hóa chế độ chuyển động tệp để giữ lại thư mục nguồn

### v1.1.1
- 2025-02-06
- Sửa chữa docker Tệp gói gương bị thiếu

### v1.1.0
- 2025-02-06
- Đã thêm chức năng di chuyển tệp，Phụ thuộc vào【[kuke2733](https://github.com/kuke2733)】Được cung cấp bởi anh chàng
- Đã thêm hiển thị số phiên bản
- Nhiệm vụ thất bại sẽ được thực hiện lại trước khi thực hiện
- Loại trừ các tệp tác vụ đã tạo trong quá trình thực thi
- Đã sửa lỗi thư mục loại trừ được tạo trong thư mục đích bug

### v1.0.8
- 2025-01-09
- Đã sửa lỗi thư mục nguồn không tồn tại bug
- Đã sửa lỗi ngoại lệ lỗi khi thư mục đích trống trong chế độ xóa
- Khắc phục trang RELENSE RENSH HIỂN THỊ EXCEP

### v1.0.7
- 2025-01-08
- Đã thêm xác minh mã thông báo
- Đã thêm chức năng tệp cấu hình nhập và xuất
- Đã sửa danh sách thả xuống bộ nhớ không được hiển thị sau khi đăng nhập
- Sửa đổi tệp cấu hình thành alist_syncbắt đầu

### v1.0.6
- 2025-01-07
- Trong chế độ xóa，Đã sửa thư mục nguồn để trống，Vấn đề của các tệp dự phòng trong thư mục đích không bị xóa chính xác
- Thích ứng đơn giản với thiết bị đầu cuối di động UI

### v1.0.5
- 2025-01-05
- ban đầuUIPhiên bản phát hành
- Hỗ trợ các chức năng đồng bộ hóa cơ bản
- ủng hộ Web Quản lý giao diện


### 2024-12-16gia hạn
- Khi kích thước của các tệp nguồn và mục tiêu không nhất quán，Nếu tệp đích được sửa đổi muộn hơn tệp nguồn，Bỏ qua ghi đè

### 2024-11-13gia hạn

- Đã sửa lỗi xóa các tệp không cần thiết trong thư mục đích 
- Tối ưu hóa các tệp dự phòng của thư mục đích đến thư mục gốc bộ nhớ
- Tối ưu hóa cài đặt cho nhiều thư mục，Một thư mục không thành công, khiến tất cả các thư mục thất bại


### 2024-09-06gia hạn
- Đã thêm tham số，Xử lý nhiều tệp hoặc thư mục trong thư mục đích，Nhưng thư mục nguồn không có Phương thức xử lý,Chức năng bởi【[RWDai](https://github.com/RWDai)】Được cung cấp bởi anh chàng 
- none Không làm gì cả 
- move Di chuyển đến thư mục đíchtrashMục lục 
- delete Xóa thực sự 

### 2024-06-29gia hạn
- MớiDIR_PAIRSSố lượng tham số,Nhiều nhất50，Các tham số phù hợp với cái trước(Ghép đôi thư mục nguồn và thư mục đích(Ghép đôi thư mục nguồn và thư mục đích，Tách biệt với dấu chấm phẩy，Tách đại tràng)),Định dạng tham số là
- ```bash
    DIR_PAIRS
    DIR_PAIRS1
    DIR_PAIRS2
    DIR_PAIRS3
    .....
    DIR_PAIRS50
    ```
  
### 2024-05-23gia hạn
- Công văn Qinglong mới

### 2024-05-13gia hạn
- 1.Logic của sự phán xét tồn tại cho các tệp mới
  - Tên tập tin 
  - Kích thước tập tin
- 2.CRON_SCHEDULE Thay đổi thành tham số thành tùy chọn
  - Thay đổi theo lịch trình nếu tham số không được truyền，Có thể hợp tác với công văn từ xa Qinglong


## Câu hỏi Phản hồi

Nếu bạn có bất kỳ vấn đề nào trong quá trình sử dụng，Vui lòng gửi Issue。


## cảnh báo
* **Vui lòng thận trọng hơn khi sử dụng chức năng xóa khi hai thư mục được sao lưu với nhau。Có thể gây mất tệp vĩnh viễn，Không có nguy cơ của riêng bạn。**



## Tips
- Các trang đầu tiên là AI phát ra，Có thể có những sai sót nhỏ trong khi sử dụng，Chào mừng bạn đến để gửi sửa chữa mã cho Master Front-end
- Lần đầu tiên sử dụng，Sau khi lưu cấu hình cơ bản，Bạn có thể nhấp để thêm một tác vụ，Làm mới danh sách thả xuống nguồn và bộ nhớ đích
- Nếu bạn quên mật khẩu của mình，Vui lòng xóadata/config/alist_sync_users_config.json tài liệu，Sẽ được thay đổi theo mặc định admin/admin
- Mã thông báo từ Alist của quản lý-cài đặt-khác Lấy，Lấy后不要重置令牌
- Có những tính năng mới khác chào mừng bạn gửi Issue。
- Điền vào thư mục đầy đủ trong tệp đồng bộ，Tham khảo hình ảnh cuối cùng
- Nếu nó không thể lấy đượcdockerGương，Bạn có thể tham khảo tập lệnh sau để thay đổi nguồn，Thực hiện mã sau ở Trung Quốc
```bash
bash <(curl -sSL https://gitee.com/xjxjin/scripts/raw/main/check_docker_registry.sh)
```
- Thực thi mã quốc tế
```bash
bash <(curl -sSL https://github.com/xjxjin/scripts/raw/main/check_docker_registry.sh)
```


## License

MIT License


## Đồng bộ hóa dữ liệu
<img src="https://raw.githubusercontent.com/xjxjin/alist-sync/main/static/images/Đồng bộ hóa dữ liệu.png" width="700" alt="Đồng bộ hóa dữ liệu">

## Tệp đồng bộ hóa
<img src="https://raw.githubusercontent.com/xjxjin/alist-sync/main/static/images/Tệp đồng bộ hóa.png" width="700" alt="Tệp đồng bộ hóa">

## Di chuyển tập tin
<img src="https://raw.githubusercontent.com/xjxjin/alist-sync/main/static/images/Di chuyển tập tin.png" width="700" alt="Di chuyển tập tin">

## Mua lại mã thông báo
<img src="https://raw.githubusercontent.com/xjxjin/alist-sync/main/static/images/Mã thông báo.png" width="700" alt="Mã thông báo获取">

## Kiểm tra tiến độ nhiệm vụ
<img src="https://raw.githubusercontent.com/xjxjin/alist-sync/main/static/images/Kiểm tra tiến độ nhiệm vụ.png" width="700" alt="Kiểm tra tiến độ nhiệm vụ">