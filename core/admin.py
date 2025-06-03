from django.contrib import admin
from .models import Survey, AnswerOption, Question, ResponseSession, UserResponse, AssignedSurvey

admin.site.register(Survey)
admin.site.register(AnswerOption)
admin.site.register(Question)
admin.site.register(UserResponse)
admin.site.register(ResponseSession)
admin.site.register(AssignedSurvey)