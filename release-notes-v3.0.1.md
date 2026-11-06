# Compteur de manifestation 3.0.1

Hotfix on 3.0.0: batched analysis crashed.

## Fixed

- **Batched analysis crashed** (`'list' object has no attribute 'ndim'`):
  ONNX Runtime's `run()` returns a LIST of outputs, and the batch path
  sliced the list instead of the tensor. Found by the operator on the very
  first real v3 analysis; fixed and proven on his footage — same count
  (122/122) at 50 img/s.

**SHA-256**: 003a9113e4ad5220ce986fca257ef693c1fb0e18336d7319c31d0a7db837c5a4
