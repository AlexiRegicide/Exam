from abc import ABC, abstractmethod
import random
import queue
import multiprocessing as mp
import time
from prettytable import PrettyTable as pt

# Константа золотого сечения
PHI = 1.618


class Question:
    def __init__(self, text: str):
        self.text = text
        self.words = text.spit()

    def get_random_word(self):
        return random.choice(self.words)

    def get_word_by_preferences(self, gender):
        a = 1/PHI
        b = (1 - a) / PHI
        probabilities = []
        if gender == "M":
            for i in range(len(self.words)):
                if i == 0:
                    probabilities.append(a)
                elif i == 1:
                    probabilities.append(b)
                else:
                    probabilities.append(
                        (1 - a - b) / (len(self.words) - 2) if len(self.words) > 2 else 0)
        else:
            for i in range(len(self.words)):
                if i == (len(self.words) - 1):
                    probabilities.append(a)
                elif i == (len(self.words) - 2):
                    probabilities.append(b)
                else:
                    probabilities.append(
                        (1 - a - b) / (len(self.words) - 2) if len(self.words) > 2 else 0)
        return random.choices(self.words, weights=probabilities, k=1)


class Person(ABC):
    @abstractmethod
    def __init__(self, name: str):
        self.name = name


class Professor(Person):
    def __init__(self, name: str, question_bank: list):
        self.name = name
        self.question_bank = question_bank
        self.total_students = 0
        self.failed_students = 0
        self.current_student = None
        self.working_time = 0
        self.last_lunch_time = 0  # Время последнего обеда
        self.is_on_lunch = False
        self.lunch_end_time = 0

    ''' 
    вопросики
    '''

    def ask_question(self, question, count=3):
        return random.sample(self.question_bank, min(count, len(self.question_bank)))

    def evaluate_question(self, student_answer, question):
        professor_answer = question.get_random_word()
        return student_answer == professor_answer

    def decide_exam_result(self, correct_answers, incorrect_answers):
        mood = random.random()
        if mood < 1/8:
            return "Провалил"
        elif mood < 1/8 + 1/4:
            return "Сдал"
        else:
            return "Сдал" if correct_answers > incorrect_answers else "Провалил"

    def calculate_exam_time(self):
        name_length = len(self.name)
        return random.uniform(name_length - 1, name_length + 1)

    '''
    обэд
    '''

    def need_lunch(self, current_time):
        return current_time - self.last_lunch_time > 30

    def go_to_lunch(self):
        self.is_on_lunch = True
        lunch_time = random.uniform(12, 18)
        self.lunch_end_time = time.time() + lunch_time
        self.last_lunch_time = time.time()
        return lunch_time

    def check_lunch_time(self):
        if self.is_on_lunch and time.time() >= self.lunch_end_time:
            self.is_on_lunch = False
            return True
        return False


class Student(Person):
    def __init__(self, name: str, gender: str):
        self.name = name
        self.gender = gender
        self.status = "Очередь"  # значение по дефолту

    def answer_question(self, question):
        return Question.get_word_by_preferences(self.gender)

    def set_status(self, status):
        self.status = status


class ExamManager:
    def __init__(self):
        self.professors = []
        self.students = []
        self.question_bank = []
        self.manager = mp.Manager()  # для создания разделяемых объектов между процессами

            # очередь студентов теперь будет разделяемым объектом
            # НЕ используем queue.Queue() здесь, так как она не работает между процессами
        self.student_queue = self.manager.Queue()

        self.results_dict = self.manager.dict()
        self.prof_stats = self.manager.dict()
        self.lock = mp.Lock()
        self.start_time = 0

        # для локального использования в методах одного процесса
        self.local_queue = queue.Queue()
    ''' 
     работа с файлами .txt
    '''

    def loading_data(self):
        self.loading_professors_from_file("examiners.txt")
        self.loading_students_from_file("students.txt")
        self.loading_questions_from_file("questions.txt")

        # Заполняем очередь студентов
        for student in self.students:
            self.student_queue.put(student)

        # Инициализируем статистику экзаменаторов
        for examiner in self.examiners:
            self.examiners_stats[examiner.name] = {
                "total_students": 0,
                "failed_students": 0,
                "current_student": "-",
                "working_time": 0
            }

        print(f"Данные успешно загружены:")
        print(f"- Экзаменаторов: {len(self.examiners)}")
        print(f"- Студентов: {len(self.students)}")
        print(f"- Вопросов: {len(self.question_bank)}")

    def loading_professors_from_file(self, filename):
        try:
            with open('examiners.txt', 'r') as file:
                for line in file:
                    professors_names = [line.strip()
                                        for line in file if line.strip()]
            self.professors = [Professor(name, [])
                               for name in professors_names]

            print(
                f"Загружено {len(self.examiners)} экзаменаторов из {filename}")

        except FileNotFoundError:
            print(f"Файл {filename} не найден")
            raise

    def loading_students_from_file(self, filename):
        try:
            with open('students.txt', 'r') as file:
                students_data = []
                for line in file:
                    line = line.strip()
                    parts = line.split(',')
                    name = parts[0].strip()
                    gender = parts[1].strip()
                    students_data.append(name, gender)
        
            self.students = [Student(name, gender)
                             for name, gender in students_data]

            print(f"Загружено {len(self.students)} студентов из {filename}")
        except FileNotFoundError:
            print(f"Файл {filename} не найден")
            raise

    def loading_questions_from_file(self, filename):
        try:
            with open('questions.txt', 'r') as file:
               question_texts = [line.strip() for line in file if line.strip()]
               self.question_bank = [Question(text) for text in question_texts]
            # обновляю дату для класса Professor()
            for professor in self.professors:
                Professor.question_bank = self.question_bank

            print(f"Загружено {len(self.question_bank)} вопросов из {filename}")
        except FileNotFoundError:
            print(f"Файл {filename} не найден")
            raise

    def professors_process(self, professor_name):
        # находим экзаменатора по имени
        professor = next(p for p in self.professors if p.name == professor_name)
        process_start_time = time.time()

        while True:
            # закончился ли обед?
            if Professor.check_lunch_time():
                with self.lock:
                    self.professors_stats[Professor.name]['текущий студент'] = '-'
                    
            # если обед, пропускаем итерацию
            if professor.is_on_lunch:
                time.sleep(0.5)
                
            try:
               student = self.student_queue.get_nowait()
            except queue.Empty:
                break
            
            # обнова инфы о текущем студенте
            with self.lock:
                Professor.current_student = student
                Professor.total_students += 1
                self.prof_stats[Professor.name] = {
                    "total_students": Professor.total_students,
                    "failed_students": Professor.failed_students,
                    "current_student": student.name,
                    "working_time": round(time.time() - self.start_time, 1)
                }
                