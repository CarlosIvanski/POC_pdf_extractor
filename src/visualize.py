import cv2

def draw_boxes(img, ocr_result):
    img_copy = img.copy()
    n_boxes = len(ocr_result['level'])

    for i in range(n_boxes):
        (x, y, w, h) = (ocr_result['left'][i], ocr_result['top'][i], 
                        ocr_result['width'][i], ocr_result['height'][i])
        text = ocr_result['text'][i]
        if len(text.strip()) > 1:
            cv2.rectangle(img_copy, (x, y), (x + w, y + h), (0, 255, 0), 2)

    return img_copy
