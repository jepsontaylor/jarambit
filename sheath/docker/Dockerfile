# Sheath solver env (PR-S1b): dolfinx 0.9.0 + gmsh (base image) + CalculiX ccx (Ubuntu apt, version pinned in evidence) + sheath deps.
# build: docker build -t jarambit-sheath:s1 sheath/docker/
FROM ghcr.io/fenics/dolfinx/dolfinx:v0.9.0
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends calculix-ccx && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir scipy==1.14.1 scikit-fem==10.0.2 shapely triangle trimesh rtree meshio matplotlib cadquery
