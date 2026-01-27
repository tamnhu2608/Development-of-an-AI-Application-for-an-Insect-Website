import numpy as np
import os
import cv2
from ultralytics import YOLO
#from tensorflow.keras.models import load_model
#from tensorflow.keras.preprocessing import image
#from tensorflow.keras.applications.resnet50 import preprocess_input
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

    results = model.predict(source=img_path, conf=0.25)

    if not results or len(results[0].boxes) == 0:
        return {
            "predicted_class": None,
            "bboxes": []
        }

    boxes = results[0].boxes.xyxy
    confidences = results[0].boxes.conf
    classes = results[0].boxes.cls

    results_list = []

    for i in range(len(boxes)):
        x1, y1, x2, y2 = map(float, boxes[i])
        confidence = float(confidences[i])
        class_index = int(classes[i])

        w = x2 - x1
        h = y2 - y1

        results_list.append({
            "class": class_names[class_index],
            "confidence": confidence,
            "x": x1,
            "y": y1,
            "width": w,
            "height": h,
        })

    best_index = confidences.argmax().item()
    predicted_class = class_names[int(classes[best_index])]

    return {
        "predicted_class": predicted_class,
        "bboxes": results_list
    }



import tempfile
from django.core.files.storage import default_storage
import uuid

def predict_top_species(image_file, top_k=3):
    model_path = os.path.join(settings.MEDIA_ROOT, 'model', 'best_yolo11n_ip103.pt')
    model = YOLO(model_path)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        for chunk in image_file.chunks():
            tmp.write(chunk)
        img_path = tmp.name

    results = model.predict(source=img_path, conf=0.25)

    if not results or len(results[0].boxes) == 0:
        return [], None, []

    boxes = results[0].boxes
    class_scores = {}
    bboxes = []

    image = cv2.imread(img_path)

    for box in boxes:
        cls = int(box.cls.item())
        conf = float(box.conf.item())
        x1, y1, x2, y2 = map(int, box.xyxy[0])

        class_scores[cls] = max(class_scores.get(cls, 0), conf)

        bboxes.append({
            "class": class_names[cls],
            "confidence": conf,
            "x": x1,
            "y": y1,
            "width": x2 - x1,
            "height": y2 - y1
        })

        # vẽ bbox
        cv2.rectangle(image, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            image,
            f"{class_names[cls]} {conf:.2f}",
            (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1
        )

    filename = f"bbox_{uuid.uuid4().hex}.jpg"
    save_path = os.path.join(settings.MEDIA_ROOT, "bbox_predictions", filename)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    cv2.imwrite(save_path, image)

    bbox_image_url = settings.MEDIA_URL + "bbox_predictions/" + filename

    top = sorted(class_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    return (
        [{"class_name": class_names[c], "confidence": score} for c, score in top],
        bbox_image_url,
        bboxes
    )