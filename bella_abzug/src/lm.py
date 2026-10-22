import mediapipe as mp, numpy as np, sys
from mediapipe.tasks.python import vision, BaseOptions
img=mp.Image.create_from_file(sys.argv[1])
opt=vision.FaceLandmarkerOptions(base_options=BaseOptions(model_asset_path='models/face_landmarker.task'),output_facial_transformation_matrixes=True,num_faces=1)
r=vision.FaceLandmarker.create_from_options(opt).detect(img)
lm=np.array([[p.x,p.y,p.z] for p in r.face_landmarks[0]])
W,H=img.width,img.height
lm[:,0]*=W; lm[:,1]*=H; lm[:,2]*=W
np.save('lm.npy',lm); np.save('mat.npy',np.array(r.facial_transformation_matrixes[0]))
print(W,H,lm.shape,lm.min(0),lm.max(0)); print(np.array(r.facial_transformation_matrixes[0]).round(3))
