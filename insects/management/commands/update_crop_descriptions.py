

from django.core.management.base import BaseCommand
from insects.models import Crop

class Command(BaseCommand):
    help = "Cập nhật mô tả chi tiết 30 cây trồng Việt Nam (giữ nguyên các cột khác)"

    def handle(self, *args, **options):
        crop_descriptions = {
            "Lúa": "Cây lúa là cây thân thảo hàng năm, rễ chùm, lá dài hẹp, thân rỗng chia đốt. Giai đoạn sinh trưởng từ gieo mạ đến thu hoạch khoảng 3–6 tháng. Lúa là cây trồng chủ lực tại Việt Nam, có lịch sử canh tác hàng nghìn năm, quan trọng về an ninh lương thực và xuất khẩu gạo.",
            "Ngô": "Ngô là cây thân thảo cao, lá to, hoa đực mọc ở ngọn, hoa cái ở nách lá. Thời gian sinh trưởng khoảng 3–5 tháng. Ngô được trồng rộng rãi ở Trung du miền núi Bắc Bộ và Tây Nguyên, dùng làm lương thực, thức ăn chăn nuôi và nguyên liệu công nghiệp.",
            "Khoai lang": "Khoai lang là cây thân bò, rễ phình thành củ chứa tinh bột, sinh trưởng nhanh 3–5 tháng. Là cây lương thực và thực phẩm phổ biến, góp phần tăng thu nhập nông hộ tại Bắc Trung Bộ và Đồng bằng sông Cửu Long.",
            "Khoai tây": "Khoai tây là cây thân thảo, củ hình dạng tròn hoặc bầu dục, thời gian sinh trưởng 90–120 ngày. Trồng chủ yếu ở Đà Lạt và miền núi phía Bắc, là thực phẩm và nguyên liệu chế biến công nghiệp.",
            "Sắn": "Sắn (khoai mì) là cây thân gỗ nhỏ, rễ củ lớn chứa tinh bột, sinh trưởng 8–12 tháng. Chủ yếu trồng tại Tây Nguyên và trung du miền núi, dùng làm tinh bột, thức ăn chăn nuôi và ethanol.",
            "Cà chua": "Cà chua là cây thân thảo, lá kép, quả mọng nhiều hạt, sinh trưởng 70–90 ngày. Trồng rộng rãi ở Đồng bằng sông Hồng và Lâm Đồng, giá trị kinh tế cao trong rau quả.",
            "Ớt": "Ớt là cây thân thảo, quả mọng chứa capsaicin, sinh trưởng 90–120 ngày. Là gia vị xuất khẩu quan trọng, trồng chủ yếu ở Miền Trung và Tây Nguyên.",
            "Cà tím": "Cà tím là cây thân thảo, quả lớn màu tím đặc trưng, thời gian sinh trưởng 90–120 ngày. Rau ăn quả phổ biến tại Miền Bắc và Đà Lạt.",
            "Dưa leo": "Dưa leo là cây thân bò, có tua cuốn, quả dài, sinh trưởng 50–70 ngày. Trồng để ăn quả tươi, phổ biến ở Đồng bằng sông Hồng và Nam Bộ.",
            "Bắp cải": "Bắp cải là cây thân ngắn, lá cuốn thành bắp, sinh trưởng 60–90 ngày. Rau ăn lá chủ lực, trồng ở miền Bắc vụ đông và Đà Lạt.",
            "Cải xanh": "Cải xanh là rau xanh phổ biến, thân thảo, lá xanh đậm, sinh trưởng 30–60 ngày. Trồng rộng rãi trên toàn quốc.",
            "Hành": "Hành là cây thân thảo, lá rỗng, thân củ, sinh trưởng 90–120 ngày. Gia vị quan trọng trong ẩm thực Việt Nam, chủ yếu ở miền Bắc.",
            "Tỏi": "Tỏi là cây thân thảo, củ nhiều tép, sinh trưởng 150–180 ngày. Gia vị và dược liệu, trồng phổ biến tại miền Bắc.",
            "Đậu cô ve": "Đậu cô ve là cây thân leo, quả dạng đậu dài, sinh trưởng 60–90 ngày. Là rau thực phẩm cung cấp đạm thực vật, trồng ở Đồng bằng.",
            "Đậu nành": "Đậu nành là cây thân thảo, quả dạng đậu, sinh trưởng 90–120 ngày. Nguồn đạm thực vật và nguyên liệu công nghiệp, trồng tại Đông Nam Bộ.",
            "Cà phê": "Cà phê là cây thân gỗ nhỏ, lá xanh bóng, quả mọng, sinh trưởng 3–5 năm mới cho quả. Trồng chủ yếu ở Tây Nguyên, xuất khẩu chủ lực của Việt Nam.",
            "Cao su": "Cao su là cây thân gỗ lớn, cho mủ trắng, sinh trưởng 6–7 năm mới khai thác mủ. Trồng tại Đông Nam Bộ và Tây Nguyên, nguyên liệu công nghiệp.",
            "Hồ tiêu": "Hồ tiêu là cây dây leo, quả mọc thành chùm, sinh trưởng 3–4 năm. Gia vị xuất khẩu giá trị cao, trồng chủ yếu ở Tây Nguyên.",
            "Chè": "Chè là cây thân gỗ nhỏ hoặc bụi, sinh trưởng 2–3 năm. Nguyên liệu sản xuất đồ uống, trồng tại trung du miền núi phía Bắc.",
            "Mía": "Mía là cây thân cao nhiều đốt chứa dịch ngọt, sinh trưởng 12–18 tháng. Nguyên liệu sản xuất đường, trồng chủ yếu Tây Nam Bộ.",
            "Điều": "Điều là cây thân gỗ, quả giả hình quả lê, sinh trưởng 4–5 năm. Là cây xuất khẩu hạt, trồng tại Đông Nam Bộ.",
            "Cam": "Cam là cây thân gỗ, quả có múi, sinh trưởng 3–5 năm. Trồng phổ biến tại Nam Bộ, tiêu thụ nội địa và xuất khẩu.",
            "Quýt": "Quýt là cây thân gỗ, quả nhỏ có múi, sinh trưởng 3–5 năm. Trồng tại Nam Bộ, đặc sản vùng miền.",
            "Bưởi": "Bưởi là cây thân gỗ, quả lớn nhiều múi, sinh trưởng 4–6 năm. Trồng chủ yếu Nam Bộ, giá trị kinh tế cao.",
            "Xoài": "Xoài là cây thân gỗ lớn, quả hạch, sinh trưởng 4–5 năm. Trồng tại Nam Bộ, cây xuất khẩu chủ lực.",
            "Chuối": "Chuối là cây thân giả, rễ chùm, sinh trưởng 9–12 tháng. Trồng tại Nam Bộ, phổ biến và xuất khẩu.",
            "Nhãn": "Nhãn là cây thân gỗ, quả tròn, sinh trưởng 3–4 năm. Trồng tại miền Bắc, đặc sản trái cây.",
            "Vải": "Vải là cây thân gỗ, quả mọc thành chùm, sinh trưởng 3–4 năm. Trồng tại miền Bắc, đặc sản xuất khẩu.",
            "Thanh long": "Thanh long là cây thân mọng nước dạng xương rồng, sinh trưởng 1–2 năm. Trồng chủ yếu Nam Trung Bộ, xuất khẩu chủ lực.",
            "Ổi": "Ổi là cây thân gỗ nhỏ, quả nhiều hạt, sinh trưởng 2–3 năm. Trồng toàn quốc, tiêu thụ mạnh nội địa."
        }

        updated = 0
        missing = []

        for name, desc in crop_descriptions.items():
            try:
                crop = Crop.objects.get(name=name)
                crop.description = desc
                crop.save()
                updated += 1
            except Crop.DoesNotExist:
                missing.append(name)

        self.stdout.write(self.style.SUCCESS(f"Đã cập nhật {updated} cây trồng"))
        if missing:
            self.stdout.write(self.style.WARNING(f"Không tìm thấy {len(missing)} cây: {', '.join(missing)}"))