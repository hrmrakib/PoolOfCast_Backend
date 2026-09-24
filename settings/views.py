from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.core.mail import send_mail
from .models import *
from .serializers import *
from core.pagination import CustomPagination
from drf_spectacular.utils import extend_schema
class PrivacyPolicyListCreateAPIView(APIView):

    def get_object(self):
        try:
            return PrivacyPolicy.objects.all().first()
        except PrivacyPolicy.DoesNotExist:
            return None

    def get(self, request):
        policies = PrivacyPolicy.objects.all().order_by('-created_on')
        paginator = CustomPagination()
        paginated_policies = paginator.paginate_queryset(policies, request, view=self)
        serializer = PrivacyPolicySerializer(paginated_policies, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=PrivacyPolicySerializer,
        responses={201: PrivacyPolicySerializer}
    )
    def post(self, request):
        get_privacy_policy = PrivacyPolicy.objects.all()
        if get_privacy_policy:
            return Response({'status':False,"status_code": 400,'message':'data already exist.'})
        serializer = PrivacyPolicySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': True,"status_code": 201, 'data': serializer.data}, status=status.HTTP_201_CREATED)
        return Response({'status': False,"status_code": 400, 'message': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        policy = self.get_object()
        if not policy:
            return Response({'status': False,"status_code": 404, 'message': 'Privacy policy not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = PrivacyPolicySerializer(policy, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': True,"status_code": 200, 'data': serializer.data})
        return Response({'status': False,"status_code": 400, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        policy = self.get_object()
        if not policy:
            return Response({'status': False,"status_code": 404, 'message': 'Privacy policy not found'}, status=status.HTTP_404_NOT_FOUND)
        policy.delete()
        return Response({'status': True,"status_code": 204, 'message': 'Privacy policy deleted'}, status=status.HTTP_204_NO_CONTENT)

class TermsAndConditionsListCreateAPIView(APIView):

    def get_object(self):
        try:
            return TermsAndCondition.objects.all().first()
        except TermsAndCondition.DoesNotExist:
            return None

    def get(self, request):
        terms = TermsAndCondition.objects.all().order_by('-created_on')
        paginator = CustomPagination()
        paginated_terms = paginator.paginate_queryset(terms, request, view=self)
        serializer = TermsAndConditionSerializer(paginated_terms, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=TermsAndConditionSerializer,
        responses={201: TermsAndConditionSerializer}
    )
    def post(self, request):
        get_terms = TermsAndCondition.objects.all()
        if get_terms:
            return Response({'status':False,"status_code": 400,'message':'data already exist.'})
        serializer = TermsAndConditionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': True,"status_code": 201, 'data': serializer.data}, status=status.HTTP_201_CREATED)
        return Response({'status': False,"status_code": 400, 'message': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        terms = self.get_object()
        if not terms:
            return Response({'status': False,"status_code": 404, 'message': 'Terms and conditions not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = TermsAndConditionSerializer(terms, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': True,"status_code": 200, 'data': serializer.data})
        return Response({'status': False,"status_code": 400, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        terms = self.get_object()
        if not terms:
            return Response({'status': False,"status_code": 404, 'message': 'Terms and conditions not found'}, status=status.HTTP_404_NOT_FOUND)
        terms.delete()
        return Response({'status': True,"status_code": 204, 'message': 'Terms and conditions deleted'}, status=status.HTTP_204_NO_CONTENT)
    
class AboutUsListCreateAPIView(APIView):

    def get_object(self):
        try:
            return AboutUs.objects.all().first()
        except AboutUs.DoesNotExist:
            return None

    def get(self, request):
        about_us = AboutUs.objects.all().order_by('-created_on')
        paginator = CustomPagination()
        paginated_about = paginator.paginate_queryset(about_us, request, view=self)
        serializer = AboutUsSerializer(paginated_about, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        request=AboutUsSerializer,
        responses={201: AboutUsSerializer}
    )
    def post(self, request):
        get_about_us = AboutUs.objects.all()
        if get_about_us:
            return Response({'status':False,"status_code": 400,'message':'data already exist.'})
        serializer = AboutUsSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': True,"status_code": 201, 'data': serializer.data}, status=status.HTTP_201_CREATED)
        return Response({'status': False,"status_code": 400, 'message': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request):
        about_us = self.get_object()
        if not about_us:
            return Response({'status': False,"status_code": 404, 'message': 'About us not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = AboutUsSerializer(about_us, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'status': True,"status_code": 200, 'data': serializer.data})
        return Response({'status': False,"status_code": 400, 'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        about_us = self.get_object()
        if not about_us:
            return Response({'status': False,"status_code": 404, 'message': 'About us not found'}, status=status.HTTP_404_NOT_FOUND)
        about_us.delete()
        return Response({'status': True,"status_code": 204, 'message': 'About us deleted'}, status=status.HTTP_204_NO_CONTENT)



class ContactMessageCreateAPIView(APIView):
    @extend_schema(
        request=ContactMessageSerializer,
        responses={201: ContactMessageSerializer}
    )
    def post(self, request):
        serializer = ContactMessageSerializer(data=request.data)
        if serializer.is_valid():
            contact = serializer.save()

            subject = "New Contact Message Received"
            message = (
                f"First Name: {contact.first_name}\n"
                f"Last Name: {contact.last_name}\n"
                f"Email: {contact.email}\n"
                f"Phone: {contact.phone_number}\n\n"
                f"Message:\n{contact.message}"
            )

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.CONTACT_RECEIVER_EMAIL],
                fail_silently=False,
            )

            return Response(
                {
                    "status": "success",
                    "status_code": 201,
                    "message": "Your message has been submitted successfully."
                },
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
