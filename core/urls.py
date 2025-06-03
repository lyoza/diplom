from django.urls import path
from .views import upload_docx_view, upload_form, logout_view, survey_detail, survey_take, survey_delete, survey_list_for_user, permission_denied_view, CustomLoginView, survey_analysis, assign_survey
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('logout/', logout_view, name='logout'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('upload/', upload_form, name='upload_form'),  # HTML-форма
    path('api/upload-docx/', upload_docx_view, name='upload-docx'),
    path('survey/<int:pk>/', survey_detail, name='survey_detail'),
    path('survey/<int:pk>/take/', survey_take, name='survey_take'),
    path('survey/<int:pk>/delete/', survey_delete, name='survey_delete'),
    path('surveys/', survey_list_for_user, name='survey_list_for_user'),
    path('no-permission/', permission_denied_view, name='permission_denied'),
    path('survey/<int:pk>/analysis/', survey_analysis, name='survey_analysis'),
    path('survey/<int:survey_id>/assign/', assign_survey, name='assign_survey'),
]

