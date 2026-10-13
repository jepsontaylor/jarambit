"""Upscale the clean no-signature art 4x with Real-ESRGAN x4plus (spandrel), tiled, 16-bit PNG out.
python upscale_art.py IN.png OUT.png WEIGHTS.pth"""
import sys, hashlib, json, numpy as np, torch, cv2
from spandrel import ModelLoader
src, dst, w = sys.argv[1:4]
m = ModelLoader().load_from_file(w).model.cuda().eval().half()
img = cv2.imread(src, cv2.IMREAD_COLOR)[:, :, ::-1].astype(np.float32) / 255.0
H, W, _ = img.shape; T, P, S = 256, 16, 4
out = np.zeros((H * S, W * S, 3), np.float32)
with torch.no_grad():
    for y in range(0, H, T):
        for x in range(0, W, T):
            y0, x0 = max(y - P, 0), max(x - P, 0); y1, x1 = min(y + T + P, H), min(x + T + P, W)
            t = torch.from_numpy(img[y0:y1, x0:x1].transpose(2, 0, 1)).unsqueeze(0).cuda().half()
            o = m(t)[0].float().clamp(0, 1).cpu().numpy().transpose(1, 2, 0)
            oy, ox = (y - y0) * S, (x - x0) * S; h, ww = min(T, H - y) * S, min(T, W - x) * S
            out[y * S:y * S + h, x * S:x * S + ww] = o[oy:oy + h, ox:ox + ww]
cv2.imwrite(dst, (out[:, :, ::-1] * 65535 + 0.5).astype(np.uint16))
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
json.dump({'src': src, 'src_sha256': sha(src), 'weights_sha256': sha(w), 'model': 'RealESRGAN_x4plus',
           'size': [W * S, H * S], 'bit_depth': 16, 'out_sha256': sha(dst)}, open(dst + '.json', 'w'), indent=1)
print('ok', W * S, H * S)
