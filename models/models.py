from fastapi import APIRouter, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from PIL import Image
import torch
from transformers import BlipProcessor, BlipForConditionalGeneration
from typing import Annotated
from auth import get_current_user
from io import BytesIO


router = APIRouter()

user_dependency = Annotated[dict, Depends(get_current_user)]

processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)


@router.post("/caption")
async def caption(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        img = Image.open(BytesIO(image_bytes)).convert("RGB")
        # Preprocess
        inputs = processor(images=img, return_tensors="pt").to(device)
        # Generate caption
        outputs = model.generate(**inputs, max_length=40)
        caption = processor.decode(outputs[0], skip_special_tokens=True)
        return JSONResponse({"caption": caption})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})