## torrent

- `DELETE /api/v1/torrent/cache` — 清理种子缓存
- `GET /api/v1/torrent/cache` — 获取种子缓存
- `POST /api/v1/torrent/cache/refresh` — 刷新种子缓存
- `POST /api/v1/torrent/cache/reidentify/{domain}/{torrent_hash}` — 重新识别种子
- `DELETE /api/v1/torrent/cache/{domain}/{torrent_hash}` — 删除指定种子缓存
