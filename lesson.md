Source: https://lessons.md

# service-delivery-record Lessons.md

This service should not carry a production `CMD runserver` in its Dockerfile. On ECS, that overrides the default branch in `entrypoint.sh` and skips `migrate + gunicorn`.

The failure shape is easy to misread. `/health/` can still return `200` while `/records/` returns `500`, because Django starts and serves requests before the missing tables are exercised.

The safe production container contract is:

- `ENTRYPOINT ["./entrypoint.sh"]`
- no Dockerfile `CMD runserver`
- `entrypoint.sh` owns `python manage.py migrate --noinput`
- `entrypoint.sh` ends with gunicorn on `0.0.0.0:8000`

For Slice 3 on `ev-dashboard.com`, the honest smoke path was `/api/delivery-record/records/`, not the prefix root `/api/delivery-record/`.
