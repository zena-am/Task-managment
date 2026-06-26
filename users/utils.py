from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

def notify_existing_user(email, sender_name, workspace_name):
    subject = 'New Project Invitation'
    text_message = 'You have been invited to join a new project team. Please log in to the app to accept.'

    html_content = render_to_string('SendEmails/existing_user_invite.html',{'sender_name': sender_name,
        'workspace_name': workspace_name})

    send_mail(
        subject=subject,
        message=text_message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[email],
        html_message=html_content,
        fail_silently=True,
    )


def notify_new_user(email, sender_name, workspace_name):
    subject = ' You’re invited to join our workspace!'
    text_message = 'A teammate has invited you to collaborate. Download our app and create an account using this email.'

    html_content = render_to_string('SendEmails/new_user_invite.html',{'sender_name': sender_name,
        'workspace_name': workspace_name})

    send_mail(
        subject=subject,
        message=text_message,
        from_email=settings.EMAIL_HOST_USER,
        recipient_list=[email],
        html_message=html_content,
        fail_silently=False,
    )