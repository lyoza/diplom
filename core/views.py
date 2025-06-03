from django.contrib.auth import authenticate, login, logout
from .models import Survey, Question, AnswerOption, UserResponse, ResponseSession, AssignedSurvey, User
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from docx import Document
import re
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from django.contrib.auth.models import User

def group_required(group_name):
    def in_group(u):
        return u.is_authenticated and u.groups.filter(name=group_name).exists()
    return user_passes_test(in_group, login_url='/no-permission/' )

def permission_denied_view(request):
    return render(request, 'permission_denied.html')

class CustomLoginView(LoginView):
    template_name = 'login.html'

    def get_success_url(self):
        user = self.request.user
        if user.groups.filter(name='lead').exists():
            return reverse_lazy('upload_form')  # или куда нужно социологам
        elif user.groups.filter(name='soc').exists():
            return reverse_lazy('survey_list_for_user')  # страница списка опросов
        else:
            return reverse_lazy('permission_denied')  # если нет группы

@group_required('lead')
def upload_docx_view(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Только POST запросы разрешены')

    file_obj = request.FILES.get('file')
    if not file_obj:
        return JsonResponse({'error': 'Файл не передан'}, status=400)

    title = request.POST.get('title', 'Без названия')
    survey = Survey.objects.create(title=title, created_at=timezone.now())

    question = None
    created_questions = 0

    doc = Document(file_obj)

    for para in doc.paragraphs:
        text_block = para.text.strip().replace('\xa0', ' ').replace('\t', ' ')
        if not text_block:
            continue

        lines = text_block.splitlines()
        for text in lines:
            text = text.strip()
            if not text:
                continue

            if re.match(r'^\d+\.\s', text):
                match = re.match(r'^(\d+)\.\s', text)
                text_lower = text.lower()
                if "один вариант" in text_lower:
                    q_type = 'single'
                elif "не более" in text_lower or "несколько вариантов" in text_lower:
                    q_type = 'multiple'
                else:
                    q_type = 'single'
                q_number = match.group(1)
                question = Question.objects.create(
                    survey=survey,
                    text=text,
                    question_type=q_type,
                    question_number=q_number
                )
                created_questions += 1

            elif re.match(r'^\s*\d{3}\s*[-–]\s*', text) and question:
                match = re.match(r'^\s*(\d{3})\s*[-–]\s*(.+)', text)
                if match:
                    number = match.group(1)
                    AnswerOption.objects.create(
                        question=question,
                        text=match.group(2).strip(),
                        option_number=number
                    )

    return redirect('upload_form')
  

@group_required('lead')
def upload_form(request):
    surveys = Survey.objects.all().order_by('-created_at')
    return render(request, 'upload.html', {'surveys': surveys})

   
def logout_view(request):
    logout(request)
    return redirect('login')

@group_required('lead')
def survey_detail(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    assigned = AssignedSurvey.objects.filter(survey=survey).select_related('employee')
    assigned_employee_ids = assigned.values_list('employee_id', flat=True)
    users = User.objects.exclude(id__in=assigned_employee_ids)
    questions = survey.questions.all().prefetch_related('options')
    has_questions = questions.exists()
    has_unanswered_questions = any(q.options.count() == 0 for q in questions)

    return render(request, 'survey_detail.html', {
        'survey': survey,
        'questions': questions,
        'users': users,
        'assigned_list': assigned, 
        'has_questions': has_questions,
        'has_unanswered_questions': has_unanswered_questions,
    })


@login_required(login_url='/login/')
def survey_take(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    questions_qs = survey.questions.prefetch_related('options').all()
    questions_list = list(questions_qs)

    has_questions = bool(questions_list)
    has_all_answers = all(q.options.exists() for q in questions_list) if has_questions else False

    # Если нет вопросов или какие-то без вариантов — выводим предупреждение
    if not has_questions or not has_all_answers:
        return render(request, 'survey_take.html', {
            'survey': survey,
            'has_questions': has_questions,
            'has_all_answers': has_all_answers,
            'question': None,
            'index': 0,
            'total': 0,
            'selected_option_ids': [],
            'error': None,
        })

    # Получить сессии прохождения, связанные с пользователем и опросом
    sessions = ResponseSession.objects.filter(user=request.user, survey=survey)

    # Если есть незавершенная сессия, используем ее
    active_session = sessions.filter(completed=False).first()
    if not active_session:
        active_session = ResponseSession.objects.create(user=request.user, survey=survey)

    # Убедимся, что порядок вопросов один и тот же
    questions = survey.questions.order_by('question_number')
    total = questions.count()

    index = int(request.GET.get('index', 0))
    index = max(0, min(index, total - 1))
    question = questions[index]

    existing_response = UserResponse.objects.filter(session_id=active_session, question=question).first()
    selected_ids = list(existing_response.selected_options.values_list('id', flat=True)) if existing_response else []

    if request.method == 'POST':
        selected_option_ids = request.POST.getlist('answer')

        if not selected_option_ids:
            return render(request, 'survey_take.html', {
                'survey': survey,
                'question': question,
                'index': index,
                'total': total,
                'selected_option_ids': selected_ids,
                'error': 'Пожалуйста, выберите хотя бы один вариант ответа.',
                'has_questions': has_questions,
                'has_all_answers': has_all_answers,
            })

        selected_options = AnswerOption.objects.filter(id__in=selected_option_ids)

        if existing_response:
            existing_response.selected_options.set(selected_options)
        else:
            new_response = UserResponse.objects.create(session_id=active_session, question=question)
            new_response.selected_options.set(selected_options)

        if 'next' in request.POST and index < total - 1:
            return redirect(f"{request.path}?index={index + 1}")
        elif 'prev' in request.POST and index > 0:
            return redirect(f"{request.path}?index={index - 1}")
        elif 'save' in request.POST:
            if index == total - 1:
                active_session.completed = True
                active_session.save()
                try:
                    assigned = AssignedSurvey.objects.get(employee=request.user, survey=survey)
                    if assigned.completed_count < assigned.required_attempts:
                        assigned.completed_count += 1
                        assigned.save()
                except AssignedSurvey.DoesNotExist:
                    pass

            if request.user.groups.filter(name='СОЦИОЛОГИ').exists():
                return redirect('upload_form')
            else:
                return redirect('survey_list_for_user')

    return render(request, 'survey_take.html', {
        'survey': survey,
        'question': question,
        'index': index,
        'total': total,
        'selected_option_ids': selected_ids,
        'error': None,
        'has_questions': has_questions,
        'has_all_answers': has_all_answers,
    })

@group_required('lead')
def survey_delete(request, pk):
    survey = get_object_or_404(Survey, pk=pk)
    survey.delete()
    return redirect('upload_form')  

@group_required('soc')
def survey_list_for_user(request):
    surveys = AssignedSurvey.objects.filter(employee=request.user).select_related('survey')
    for assigned_survey in surveys:
        print(assigned_survey.survey.title)
        print(assigned_survey.survey.created_at)
    return render(request, 'survey_list.html', {'surveys': surveys})

@group_required('lead')
def survey_analysis(request, pk):
    survey = get_object_or_404(Survey, id=pk)
    questions = survey.questions.all().order_by('question_number')

    compare = request.GET.get('compare') == '1'
    other_survey_id = request.GET.get('other_survey_id')

    other_survey = None
    if compare and other_survey_id:
        try:
            other_survey = Survey.objects.get(id=other_survey_id)
        except Survey.DoesNotExist:
            other_survey = None

    paginator = Paginator(questions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    question_data = []
    for question in page_obj:
        options = question.options.all().order_by('option_number')

        total_selections = 0
        option_counts = {}

        for option in options:
            count = UserResponse.objects.filter(question=question, selected_options=option).count()
            option_counts[option.option_number] = count
            total_selections += count

        chart_data = []
        for option in options:
            count = option_counts[option.option_number]
            percent = (count / total_selections * 100) if total_selections > 0 else 0
            chart_data.append({
                'code': str(option.option_number).zfill(3),
                'text': option.text,
                'count': count,
                'percentage': percent,
            })

        comparison_chart = []
        if compare and other_survey:
            try:
                other_question = Question.objects.filter(survey=other_survey, text=question.text).order_by('question_number').first()
                other_options = other_question.options.all().order_by('option_number')
                other_total = 0
                other_counts = {}
                for opt in other_options:
                    c = UserResponse.objects.filter(question=other_question, selected_options=opt).count()
                    other_counts[opt.option_number] = c
                    other_total += c

                for opt in other_options:
                    cnt = other_counts.get(opt.option_number, 0)
                    perc = (cnt / other_total * 100) if other_total > 0 else 0
                    comparison_chart.append({
                        'text': opt.text,
                        'count': cnt,
                        'percentage': perc,
                    })
            except Question.DoesNotExist:
                comparison_chart = []

        question_data.append({
            'question': question,
            'chart': chart_data,
            'comparison_chart': comparison_chart,
        })

    similar_surveys = Survey.objects.exclude(id=survey.id).filter(
        questions__text__in=questions.values_list('text', flat=True)
    ).distinct()

    return render(request, 'survey_analysis.html', {
        'survey': survey,
        'question_data': question_data,
        'page_obj': page_obj,
        'compare': compare,
        'similar_surveys': similar_surveys,
        'selected_survey_id': int(other_survey_id) if other_survey_id else None,
        'other_survey': other_survey,
    })



@group_required('lead')
def assign_survey(request, survey_id):
    if request.method == 'POST':
        employee_id = request.POST.get('employee')
        required_attempts = int(request.POST.get('required_attempts', 1))
        employee = get_object_or_404(User, pk=employee_id)
        survey = get_object_or_404(Survey, pk=survey_id)

        AssignedSurvey.objects.create(
            survey=survey,
            employee=employee,
            required_attempts=required_attempts
        )
        return redirect('survey_detail', pk=survey.id)