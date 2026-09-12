import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import cv2
import numpy as np
from deepface import DeepFace
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_URL dan SUPABASE_SERVICE_ROLE_KEY mesti diset dalam Environment Variables."
    )

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY
)

MALAYSIA_TZ = ZoneInfo("Asia/Kuala_Lumpur")
CAPTURE_BUCKET = "capture-photos"

ALERT_EMOTIONS = {"sad", "fear", "angry"}
ALERT_CONFIDENCE_MIN = 60.0
JPEG_QUALITY = 90

app = FastAPI(
    title="e-Respons Emotion Detection API"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def malaysia_now():
    return datetime.now(MALAYSIA_TZ)


def get_child(child_id):
    response = (
        supabase.table("child_profiles")
        .select("student_id,full_name,class_name")
        .eq("id", child_id)
        .single()
        .execute()
    )

    return response.data


def upload_capture_image(frame, student_id, request_id, now):

    ok, encoded = cv2.imencode(
        ".jpg",
        frame,
        [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY],
    )

    if not ok:
        return None

    safe_student_id = str(
        student_id or "UNKNOWN"
    ).strip().replace("/", "_")

    safe_request = str(
        request_id or int(time.time())
    ).replace("/", "_")

    stamp = now.strftime("%Y%m%d_%H%M%S")

    storage_path = (
        f"{safe_student_id}/{stamp}_{safe_request}.jpg"
    )

    try:

        supabase.storage.from_(
            CAPTURE_BUCKET
        ).upload(
            storage_path,
            encoded.tobytes(),
            {
                "content-type": "image/jpeg",
                "upsert": "true",
            },
        )

        return supabase.storage.from_(
            CAPTURE_BUCKET
        ).get_public_url(
            storage_path
        )

    except Exception as e:

        print(
            "Storage upload error:",
            e
        )

        return None


def create_emergency_alert(
    child_id,
    full_name,
    class_name,
    emotion,
    confidence,
    now,
):

    normalized = emotion.lower()

    if (
        normalized not in ALERT_EMOTIONS
        or confidence < ALERT_CONFIDENCE_MIN
    ):
        return

    try:

        supabase.table(
            "emergency_alerts"
        ).insert(
            {
                "child_id": child_id,
                "alert_type": normalized.capitalize(),
                "status": "Pending",
                "triggered_at": now.isoformat(),
            }
        ).execute()

    except Exception as e:

        print(
            "Emergency alert error:",
            e
        )

    try:

        if class_name:

            teacher_response = (
                supabase.table(
                    "teacher_profiles"
                )
                .select(
                    "id,full_name,assigned_class"
                )
                .eq(
                    "assigned_class",
                    class_name
                )
                .execute()
            )

            title = (
                f"Emergency Alert - {full_name}"
            )

            message = (
                f"{full_name} menunjukkan tanda "
                f"{normalized} pada "
                f"{now.strftime('%H:%M')}"
            )

            for teacher in (
                teacher_response.data or []
            ):

                teacher_id = teacher.get(
                    "id"
                )

                if teacher_id:

                    supabase.table(
                        "notifications"
                    ).insert(
                        {
                            "recipient_id": teacher_id,
                            "recipient_role": "teacher",
                            "title": title,
                            "message": message,
                            "is_read": False,
                            "created_at": now.isoformat(),
                        }
                    ).execute()

    except Exception as e:

        print(
            "Teacher notification error:",
            e
        )


@app.get("/")
def home():

    return {
        "ok": True,
        "service": "e-Respons Emotion Detection API",
        "status": "running",
    }


@app.get("/health")
def health():

    return {
        "ok": True
    }


@app.post("/detect-emotion")
async def detect_emotion(
    file: UploadFile = File(...),
    child_id: str | None = Form(None),
    request_id: str | None = Form(None),
):

    image_bytes = await file.read()

    if not image_bytes:

        raise HTTPException(
            status_code=400,
            detail="Gambar kosong."
        )

    image_array = np.frombuffer(
        image_bytes,
        np.uint8
    )

    frame = cv2.imdecode(
        image_array,
        cv2.IMREAD_COLOR
    )

    if frame is None:

        raise HTTPException(
            status_code=400,
            detail="Fail gambar tidak sah."
        )

    try:

        start = time.time()

        result = DeepFace.analyze(
            img_path=frame,
            actions=["emotion"],
            detector_backend="opencv",
            enforce_detection=False, # Supaya tak throw error terus kalau muka kurang jelas
            silent=True,
        )

        if isinstance(result, list):

            result = result[0]

        emotion = str(
            result["dominant_emotion"]
        )

        confidence = round(
            float(
                result["emotion"][emotion]
            ),
            2
        )

        now = malaysia_now()

        full_name = None
        student_id = None
        class_name = None
        image_url = None

        if child_id:

            try:

                child = get_child(
                    child_id
                )

                student_id = child[
                    "student_id"
                ]

                full_name = child[
                    "full_name"
                ]

                class_name = child.get(
                    "class_name"
                )

            except Exception as e:

                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Pelajar tidak dijumpai: {e}"
                    ),
                )

            supabase.table(
                "emotion_logs"
            ).insert(
                {
                    "child_id": child_id,
                    "emotion_type": emotion.capitalize(),
                    "confidence_score": confidence,
                    "detected_at": now.isoformat(),
                }
            ).execute()

            image_url = upload_capture_image(
                frame,
                student_id,
                request_id,
                now,
            )

            if (
                emotion.lower()
                in ALERT_EMOTIONS
                and confidence
                >= ALERT_CONFIDENCE_MIN
            ):

                create_emergency_alert(
                    child_id,
                    full_name,
                    class_name,
                    emotion,
                    confidence,
                    now,
                )

        elapsed = round(
            time.time() - start,
            2
        )

        return {

            "ok": True,

            "emotion": emotion,

            "confidence": confidence,

            "child_id": child_id,

            "student_id": student_id,

            "full_name": full_name,

            "class_name": class_name,

            "image_url": image_url,

            "is_alert": (
                emotion.lower()
                in ALERT_EMOTIONS
                and confidence
                >= ALERT_CONFIDENCE_MIN
            ),

            "captured_at": now.isoformat(),

            "processing_time": elapsed,
        }

    except HTTPException:

        raise

    except Exception as e:

        print(
            "Emotion detection error:",
            e
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Gagal analisis emosi: {e}"
            ),
        )
