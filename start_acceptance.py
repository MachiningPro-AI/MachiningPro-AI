import os
os.environ["MACHININGPRO_DEV_USERNAME"] = "demo"
os.environ["MACHININGPRO_DEV_PASSWORD"] = "A1234"
os.environ["MACHININGPRO_DEV_JWT_SECRET"] = "machiningpro-local-dev-jwt-secret-00001"
os.environ["MACHININGPRO_CUTTING_PARAM_REF_PATH"] = "D:/makina_ogrenmesi/MachiningPro_AI_NEXT/data/cutting_param_reference.md"
import uvicorn
uvicorn.run("backend.api.app:app", host="127.0.0.1", port=8766)
