import sys, shutil; sys.path.insert(0,'tools/atlas_upscale')
import bridge, numpy as np
from PIL import Image, ImageFilter
c=bridge.call
N=int(sys.argv[1]); sets=sys.argv[2].split(","); out=sys.argv[3]
box=(1500,380,2500,1280)
import pathlib; pathlib.Path(out).mkdir(parents=True,exist_ok=True)
frames={}
c("timescale",value=1)
for s in sets:
    print(c("texture_set",name=s).get("ok")); c("zoom",value=0.45); c("wait",frames=150)
    L=[]
    for i in range(N):
        r=c("shot",name=f"b_{s.replace(' ','_')}_{i}")
        im=Image.open(bridge.to_linux(r["path"])).convert("RGB").crop(box); L.append(im)
        c("wait",frames=7)
    frames[s]=L
def low(im): return np.asarray(im.convert("L").resize((50,45),Image.BOX).filter(ImageFilter.GaussianBlur(1)),float)
ref=low(frames[sets[0]][0])
best={}
for s in sets:
    ds=[np.abs(low(im)-ref).mean() for im in frames[s]]
    k=int(np.argmin(ds)); best[s]=(k,ds[k]); frames[s][k].save(f"{out}/{s.replace(' ','_')}.png")
print(best)
