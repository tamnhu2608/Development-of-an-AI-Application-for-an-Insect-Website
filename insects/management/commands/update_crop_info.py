from django.core.management.base import BaseCommand
from insects.models import Crop


class Command(BaseCommand):
    help = "Cập nhật thông tin chi tiết cây trồng Việt Nam (chuẩn nông nghiệp)"

    def handle(self, *args, **options):

        crop_data = {
            "Lúa": (
                "Cây lương thực chủ lực, đảm bảo an ninh lương thực quốc gia và xuất khẩu gạo.",
                "Cây thân thảo một năm, rễ chùm, thân rỗng chia đốt, lá dài hẹp.",
                "Đồng bằng sông Cửu Long, Đồng bằng sông Hồng"
            ),
            "Ngô": (
                "Nguyên liệu quan trọng cho thức ăn chăn nuôi và công nghiệp chế biến.",
                "Cây thân thảo cao, thân đặc, lá lớn; hoa đực ở ngọn, hoa cái ở nách lá.",
                "Trung du miền núi phía Bắc, Tây Nguyên"
            ),
            "Khoai lang": (
                "Nguồn thực phẩm và tinh bột, góp phần tăng thu nhập nông hộ.",
                "Cây thân bò, rễ phình thành củ chứa tinh bột.",
                "Bắc Trung Bộ, Đồng bằng sông Cửu Long"
            ),
            "Khoai tây": (
                "Thực phẩm và nguyên liệu công nghiệp chế biến.",
                "Cây thân thảo, thân ngầm phát triển thành củ.",
                "Đồng bằng sông Hồng, Đà Lạt"
            ),
            "Sắn": (
                "Nguyên liệu sản xuất tinh bột và ethanol.",
                "Cây thân gỗ nhỏ, rễ củ lớn chứa nhiều tinh bột.",
                "Tây Nguyên, Trung du miền núi"
            ),
            "Cà chua": (
                "Rau quả có giá trị dinh dưỡng và kinh tế cao.",
                "Cây thân thảo, lá kép, quả mọng nhiều hạt.",
                "Đồng bằng sông Hồng, Lâm Đồng"
            ),
            "Ớt": (
                "Gia vị quan trọng và mặt hàng xuất khẩu.",
                "Cây thân thảo, quả mọng chứa capsaicin.",
                "Miền Trung, Tây Nguyên"
            ),
            "Cà tím": (
                "Rau ăn quả phổ biến trong tiêu dùng nội địa.",
                "Cây thân thảo, quả lớn màu tím đặc trưng.",
                "Miền Bắc, Đà Lạt"
            ),
            "Dưa leo": (
                "Rau ăn quả ngắn ngày, tiêu thụ mạnh.",
                "Cây thân bò, có tua cuốn, quả dài.",
                "Đồng bằng sông Hồng, Nam Bộ"
            ),
            "Bắp cải": (
                "Rau ăn lá chủ lực trong khẩu phần.",
                "Cây thân ngắn, lá cuốn thành bắp.",
                "Miền Bắc vụ đông, Đà Lạt"
            ),
            "Cải xanh": (
                "Rau xanh phổ biến, ngắn ngày.",
                "Cây thân thảo, lá xanh đậm.",
                "Toàn quốc"
            ),
            "Hành": (
                "Gia vị quan trọng trong chế biến thực phẩm.",
                "Cây thân thảo, lá rỗng, thân củ.",
                "Miền Bắc"
            ),
            "Tỏi": (
                "Gia vị và dược liệu.",
                "Cây thân thảo, thân củ nhiều tép.",
                "Miền Bắc"
            ),
            "Đậu cô ve": (
                "Rau thực phẩm cung cấp đạm thực vật.",
                "Cây thân leo, quả dạng đậu dài.",
                "Đồng bằng"
            ),
            "Đậu nành": (
                "Nguồn đạm thực vật và nguyên liệu công nghiệp.",
                "Cây thân thảo, quả dạng đậu.",
                "Đông Nam Bộ"
            ),
            "Cà phê": (
                "Mặt hàng nông sản xuất khẩu chủ lực.",
                "Cây thân gỗ nhỏ, lá xanh bóng, quả mọng.",
                "Tây Nguyên"
            ),
            "Cao su": (
                "Nguyên liệu cho công nghiệp chế biến cao su.",
                "Cây thân gỗ lớn, cho mủ trắng.",
                "Đông Nam Bộ, Tây Nguyên"
            ),
            "Hồ tiêu": (
                "Gia vị xuất khẩu có giá trị kinh tế cao.",
                "Cây dây leo, quả mọc thành chùm.",
                "Tây Nguyên"
            ),
            "Chè": (
                "Nguyên liệu sản xuất đồ uống.",
                "Cây thân gỗ nhỏ hoặc cây bụi.",
                "Trung du miền núi phía Bắc"
            ),
            "Mía": (
                "Nguyên liệu chính cho sản xuất đường.",
                "Cây thân cao nhiều đốt chứa dịch ngọt.",
                "Tây Nam Bộ"
            ),
            "Điều": (
                "Xuất khẩu hạt điều.",
                "Cây thân gỗ, quả giả hình quả lê.",
                "Đông Nam Bộ"
            ),
            "Cam": (
                "Trái cây tiêu thụ nội địa và xuất khẩu.",
                "Cây thân gỗ, quả có múi.",
                "Nam Bộ"
            ),
            "Quýt": (
                "Trái cây đặc sản vùng miền.",
                "Cây thân gỗ, quả nhỏ có múi.",
                "Nam Bộ"
            ),
            "Bưởi": (
                "Trái cây có giá trị kinh tế cao.",
                "Cây thân gỗ, quả lớn nhiều múi.",
                "Nam Bộ"
            ),
            "Xoài": (
                "Trái cây xuất khẩu chủ lực.",
                "Cây thân gỗ lớn, quả hạch.",
                "Nam Bộ"
            ),
            "Chuối": (
                "Trái cây phổ biến và xuất khẩu.",
                "Cây thân giả, rễ chùm.",
                "Nam Bộ"
            ),
            "Nhãn": (
                "Trái cây đặc sản.",
                "Cây thân gỗ, quả tròn.",
                "Miền Bắc"
            ),
            "Vải": (
                "Trái cây đặc sản xuất khẩu.",
                "Cây thân gỗ, quả mọc thành chùm.",
                "Miền Bắc"
            ),
            "Thanh long": (
                "Trái cây xuất khẩu chủ lực.",
                "Cây thân mọng nước dạng xương rồng.",
                "Nam Trung Bộ"
            ),
            "Ổi": (
                "Trái cây tiêu thụ mạnh trong nước.",
                "Cây thân gỗ nhỏ, quả nhiều hạt.",
                "Toàn quốc"
            ),
        }

        updated = 0
        missing = []

        for name, (eco, morph, area) in crop_data.items():
            try:
                crop = Crop.objects.get(name=name)
                crop.economic_value = eco
                crop.morphology = morph
                crop.cultivation_area = area
                crop.save()
                updated += 1
            except Crop.DoesNotExist:
                missing.append(name)

        self.stdout.write(self.style.SUCCESS(f"Đã cập nhật {updated} cây trồng"))

        if missing:
            self.stdout.write(self.style.WARNING(
                f"Không tìm thấy {len(missing)} cây: {', '.join(missing)}"
            ))

