# e-Respons Emotion Detection API

Flutter uploads a captured image to the FastAPI endpoint:

POST /detect-emotion

The API runs DeepFace emotion detection and, when `child_id` is supplied:
- reads the student profile from Supabase
- saves the emotion to `emotion_logs`
- uploads the image to `capture-photos`
- creates an emergency alert for Sad/Fear/Angry at 60% or higher
- notifies teachers assigned to the student's class

## Render Environment Variables

Set:
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY

Do not put the service-role key inside GitHub code.
