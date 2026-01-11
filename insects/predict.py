import numpy as np
import os
import cv2
from ultralytics import YOLO
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
from tensorflow.keras.applications.resnet50 import preprocess_input
from django.conf import settings

class_names = [
    'Rice leaf roller',    'Rice leaf caterpillar',    'Paddy stem maggot',    'Asiatic rice borer',    'Yellow rice borer',
    'Rice gall midge',    'Rice Stemfly',    'Brown plant hopper',    'White backed plant hopper',    'Small brown plant hopper',
    'rice water weevil',    'rice leafhopper',    'grain spreader thrips',    'rice shell pest',    'grub',    'mole cricket',
    'wireworm',    'white margined moth',    'black cutworm',    'large cutworm',    'yellow cutworm',    'red spider',
    'corn borer',    'army worm',    'aphids',    'Potosiabre vitarsis',    'peach borer',    'english grain aphid',    'green bug',
    'bird cherry-oataphid',    'wheat blossom midge',    'penthaleus major',    'longlegged spider mite',    'wheat phloeothrips',
    'wheat sawfly',    'cerodonta denticornis',    'beet fly',    'flea beetle',    'cabbage army worm',    'beet army worm',
    'Beet spot flies',    'meadow moth',    'beet weevil',    'sericaorient alismots chulsky',    'alfalfa weevil',    'flax budworm',
    'alfalfa plant bug',    'tarnished plant bug',    'Locustoidea',    'lytta polita',    'legume blister beetle',    'blister beetle',
    'therioaphis maculata Buckton',    'odontothrips loti',    'Thrips',    'alfalfa seed chalcid',    'Pieris canidia',    'Apolygus lucorum',
    'Limacodidae',    'Viteus vitifoliae',    'Colomerus vitis',    'Brevipoalpus lewisi McGregor',    'oides decempunctata',    'Polyphagotars onemus latus',
    'Pseudococcus comstocki Kuwana',    'parathrene regalis',    'Ampelophaga',    'Lycorma delicatula',    'Xylotrechus',    'Cicadella viridis',
    'Miridae',    'Trialeurodes vaporariorum',    'Erythroneura apicalis',    'Papilio xuthus',    'Panonchus citri McGregor',
    'Phyllocoptes oleiverus ashmead',    'Icerya purchasi Maskell',    'Unaspis yanonensis',    'Ceroplastes rubens',    'Chrysomphalus aonidum',
    'Parlatoria zizyphus Lucus',    'Nipaecoccus vastalor',    'Aleurocanthus spiniferus',    'Tetradacus c Bactrocera minax',
    'Dacus dorsalis(Hendel)',    'Bactrocera tsuneonis',    'Prodenia litura',    'Adristyrannus',    'Phyllocnistis citrella Stainton',
    'Toxoptera citricidus',    'Toxoptera aurantii',    'Aphis citricola Vander Goot',    'Scirtothrips dorsalis Hood',    'Dasineura sp',
    'Lawana imitata Melichar',    'Salurnis marginella Guerr',    'Deporaus marginatus Pascoe',    'Chlumetia transversa',
    'Mango flat beak leafhopper',    'Rhytidodera bowrinii white',    'Sternochetus frigidus',    'Cicadellidae'
]

def predict_image(img_path):
    model_path = os.path.join(settings.MEDIA_ROOT, 'model', 'best_yolo11n_ip103.pt')
    model = YOLO(model_path)
    results = model.predict(source=img_path)
    img = cv2.imread(img_path)
    if len(results) > 0 and len(results[0].boxes) > 0:  # Đảm bảo có đối tượng được phát hiện
        boxes = results[0].boxes.xyxy  # Toạ độ (x1, y1, x2, y2)
        confidences = results[0].boxes.conf  # Độ tin cậy
        classes = results[0].boxes.cls  # Chỉ số lớp
        results_list = []
        for i in range(len(boxes)):
            # Lấy toạ độ bounding box
            x1, y1, x2, y2 = map(int, boxes[i])  # Chuyển về kiểu int
            # Lấy độ tin cậy và nhãn lớp
            confidence = confidences[i].item()
            class_index = int(classes[i].item())
            label = f"{class_names[class_index]}: {confidence:.2f}"
            # Vẽ khung chữ nhật cho bounding box
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)  # Màu xanh đỏ
            cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            results_list.append({
                "class": class_names[class_index],
                "confidence": confidence,
                "box": [x1, y1, x2, y2]
            })
        # Lưu ảnh đã vẽ bounding box vào thư mục kết quả
        output_path = os.path.join(settings.MEDIA_ROOT, 'output_image.jpg')
        cv2.imwrite(output_path, img)
        print("Saved image with bounding boxes at:", output_path)
        # Trả về tên lớp dự đoán của đối tượng có độ tin cậy cao nhất
        best_index = confidences.argmax().item()
        predicted_class_index = int(classes[best_index])
        predicted_class_name = class_names[predicted_class_index]
        return output_path, predicted_class_name, results_list
    else:
        return "Không phát hiện đối tượng"