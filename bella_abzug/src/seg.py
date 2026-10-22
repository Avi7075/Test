import mediapipe as mp, numpy as np, sys
from mediapipe.tasks.python import vision, BaseOptions
from PIL import Image
img=mp.Image.create_from_file(sys.argv[1])
opt=vision.ImageSegmenterOptions(base_options=BaseOptions(model_asset_path='models/selfie_multiclass.tflite'),output_category_mask=True,output_confidence_masks=True)
r=vision.ImageSegmenter.create_from_options(opt).segment(img)
cm=r.category_mask.numpy_view().copy()
conf=np.stack([m.numpy_view() for m in r.confidence_masks],-1)
np.save('seg_cat.npy',cm); np.save('seg_conf.npy',conf.astype(np.float16))
print(cm.shape,np.unique(cm,return_counts=True))
pal=np.array([[0,0,0],[255,0,0],[255,200,150],[200,120,80],[0,0,255],[0,255,0]],np.uint8)
ph=np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(float)
ov=(0.5*ph+0.5*pal[cm.squeeze()]).astype(np.uint8)
Image.fromarray(ov).resize((695,1000)).save('seg_overlay.png')
