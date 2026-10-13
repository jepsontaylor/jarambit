import numpy as np
def read_msh22(p):
    with open(p) as f:
        L = f.read().split('\n')
    i = L.index('$Nodes'); n = int(L[i + 1])
    X = np.loadtxt(L[i + 2:i + 2 + n])
    ids = X[:, 0].astype(np.int64); P = X[:, 1:4]
    j = L.index('$Elements'); m = int(L[j + 1])
    tets = []
    for ln in L[j + 2:j + 2 + m]:
        a = ln.split()
        if a[1] in ('4', '11'):
            nt = int(a[2]); tets.append([int(v) for v in a[3 + nt:3 + nt + 4]])
    imap = np.zeros(ids.max() + 1, np.int64); imap[ids] = np.arange(len(ids))
    return P, imap[np.array(tets)]
