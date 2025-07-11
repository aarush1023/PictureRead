from fastapi import APIRouter, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from PIL import Image
import torch
from transformers import AutoProcessor, AutoModelForVisualQuestionAnswering
from typing import Annotated
from auth import get_current_user
from io import BytesIO
import pytesseract
from pdf2image import convert_from_bytes


router = APIRouter()

user_dependency = Annotated[dict, Depends(get_current_user)]

processor = AutoProcessor.from_pretrained("Salesforce/blip2-flan-t5-xl")
model = AutoModelForVisualQuestionAnswering.from_pretrained("Salesforce/blip2-flan-t5-xl")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)


@router.post("/caption")
async def caption(user: user_dependency, file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        if not image_bytes:
            return JSONResponse(status_code=400, content={"error": "empty file"})
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        # Preprocess
        inputs = processor(images=img, return_tensors="pt").to(device)
        # Generate caption
        outputs = model.generate(**inputs, num_beams=5, early_stopping=True, do_sample=True)
        caption = processor.decode(outputs[0], skip_special_tokens=True)

        ocr_text = pytesseract.image_to_string(img)

        return JSONResponse({"caption": caption, "text": ocr_text})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.post("/caption/pdf")
async def caption_pdf(user: user_dependency, file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        if not file_bytes:
            return JSONResponse(status_code=400, content={"error": "empty file"})

        # Convert PDF pages to images
        images = convert_from_bytes(file_bytes)

        results = []
        for i, img in enumerate(images):
            img_rgb = img.convert("RGB")

            # Caption
            inputs = processor(images=img_rgb, return_tensors="pt").to(device)
            outputs = model.generate(**inputs, num_beams=5, early_stopping=True, do_sample=True)
            caption = processor.decode(outputs[0], skip_special_tokens=True)

            # OCR
            ocr_text = pytesseract.image_to_string(img_rgb)

            results.append({
                "page": i + 1,
                "caption": caption,
                "ocr_text": ocr_text.strip()
            })

        return JSONResponse({"pages": results})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
