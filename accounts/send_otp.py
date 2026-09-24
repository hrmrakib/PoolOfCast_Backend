import random
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from email.utils import formataddr
from django.utils import timezone
from datetime import timedelta

def generate_and_send_otp(user):
    otp = str(random.randint(100000, 999999))
    user.otp = otp
    user.otp_expired_at = timezone.now() + timedelta(minutes=10)
    user.save()

    try:
        subject = 'Verify Your Identity'
        from_email = formataddr(("RIDERO", settings.EMAIL_HOST_USER))
        to = user.email
        html_content = render_to_string('otp_verification.html',{'otp':otp})
        text_content = strip_tags(html_content)
        msg = EmailMultiAlternatives(subject,text_content, from_email, [to])
        msg.attach_alternative(html_content, "text/html")
        msg.send()
        return True
    except:
        return False