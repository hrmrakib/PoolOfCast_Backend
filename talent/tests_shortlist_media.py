from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from jobs.models import Job
from talent.models import ShortlistMedia, ShortListedTalent, ShortlistOrder

User = get_user_model()


class ShortlistMediaTests(TestCase):
    def setUp(self):
        with connection.schema_editor() as se:
            for m in (Job, ShortListedTalent):
                se.create_model(m)
        self.client_user = User.objects.create_user(email="c@x.com", phone="01000000001", password="p", role="Client", is_active=True)
        self.other = User.objects.create_user(email="o@x.com", phone="01000000002", password="p", role="Client", is_active=True)
        self.job = Job.objects.create(job_id=987654,
            job_created_by_id=self.client_user.user_id, title="t", description="d",
            casting_roles="r", location="l", job_type="x", status="active", currency="$",
            created_at=timezone.now(), updated_at=timezone.now())
        self.api = APIClient()
        self.api.credentials(HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(self.client_user).access_token))
        self.url = f"/api/v1/client/talents/shortlisted/{self.job.job_id}/media/"

    def test_upload_list_delete(self):
        img = SimpleUploadedFile("a.jpg", b"x", content_type="image/jpeg")
        vid = SimpleUploadedFile("b.mp4", b"y", content_type="video/mp4")
        r = self.api.post(self.url, {"file": [img, vid], "media_date": "2026-10-01T09:30:00", "caption": "c"}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual({d["media_type"] for d in r.data["data"]}, {"image", "video"})
        self.assertIn("2026-10-01", r.data["data"][0]["media_date"])

        # public GET has the new field, existing fields intact
        pub = APIClient().get(f"/api/v1/client/talents/shortlisted/{self.job.job_id}/")
        self.assertEqual(pub.status_code, 200)
        self.assertEqual(len(pub.data["shortlist_media"]), 2)
        self.assertIn("shortlisted_talents", pub.data)

        mid = r.data["data"][0]["id"]
        d = self.api.delete(f"{self.url}{mid}/")
        self.assertEqual(d.status_code, 200)
        self.assertEqual(ShortlistMedia.objects.count(), 1)

    def test_default_date_date_only_and_validation(self):
        f = lambda n, t: SimpleUploadedFile(n, b"x", content_type=t)
        r = self.api.post(self.url, {"file": f("a.png", "image/png")}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertTrue(r.data["data"][0]["media_date"])
        r = self.api.post(self.url, {"file": f("a.png", "image/png"), "media_date": "2026-10-01"}, format="multipart")
        self.assertEqual(r.status_code, 201)
        r = self.api.post(self.url, {"file": f("a.png", "image/png"), "media_date": "junk"}, format="multipart")
        self.assertEqual(r.status_code, 400)
        r = self.api.post(self.url, {"file": f("a.txt", "text/plain")}, format="multipart")
        self.assertEqual(r.status_code, 400)
        r = self.api.post(self.url, {}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_permissions(self):
        f = SimpleUploadedFile("a.png", b"x", content_type="image/png")
        self.assertEqual(APIClient().post(self.url, {"file": f}, format="multipart").status_code, 401)
        o = APIClient()
        o.credentials(HTTP_AUTHORIZATION="Bearer " + str(RefreshToken.for_user(self.other).access_token))
        f = SimpleUploadedFile("a.png", b"x", content_type="image/png")
        self.assertEqual(o.post(self.url, {"file": f}, format="multipart").status_code, 403)
