from django.db import models
from django.contrib.auth.models import User

class Survey(models.Model):
    title = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)  

class Question(models.Model):
    QUESTION_TYPES = [
        ('single', 'Один вариант'),
        ('multiple', 'Несколько вариантов'),
    ]
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    question_number = models.CharField(max_length=3)

class AnswerOption(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=255)
    option_number = models.IntegerField(max_length=3)

class ResponseSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE)
    completed = models.BooleanField(default=False)

class UserResponse(models.Model):
    session_id = models.ForeignKey(ResponseSession, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_options = models.ManyToManyField(AnswerOption)

class AssignedSurvey(models.Model):
    survey = models.ForeignKey('Survey', on_delete=models.CASCADE)
    employee = models.ForeignKey(User, on_delete=models.CASCADE)
    required_attempts = models.PositiveIntegerField(default=1)
    assigned_at = models.DateTimeField(auto_now_add=True)
    completed_count = models.PositiveIntegerField(default=0)

