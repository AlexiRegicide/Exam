from abc import ABC, abstractmethod
import random
import queue
import multiprocessing as mp
import time
from tabulate import tabulate
import os
import sys

#* константа золотого сечения
PHI = 1.618


class Question:
    def __init__(self, text: str):
        self.text = text
        self.words = text.split()

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
        self.last_lunch_time = 0  # время последнего обеда
        self.is_on_lunch = False
        self.lunch_end_time = 0

    #* вопросики
    def ask_question(self, question, count=3):
        # выбираем 3 случайных вопроса 
        return random.sample(self.question_bank, min(count, len(self.question_bank)))

    def evaluate_question(self, student_answer, question):
        # оцениваем ответ студента
        professor_answer = question.get_random_word()
        return student_answer == professor_answer

    def decide_exam_result(self, correct_answers, incorrect_answers):
        # профессор принимает решение
        mood = random.random()
        if mood < 1/8:
            return "Провалил"
        elif mood < 1/8 + 1/4:
            return "Сдал"
        else:
            return "Сдал" if correct_answers > incorrect_answers else "Провалил"

    def calculate_exam_time(self):
        # рассчитываем время экзамена на основе длины имени
        name_length = len(self.name)
        return random.uniform(name_length - 1, name_length + 1)

    #* обэд
    def need_lunch(self, current_time):
        # проверяем нужен ли обед
        return current_time - self.last_lunch_time > 30

    def go_to_lunch(self):
        # профессор идет на обед
        self.is_on_lunch = True
        lunch_time = random.uniform(12, 18)
        self.lunch_end_time = time.time() + lunch_time
        self.last_lunch_time = time.time()
        return lunch_time

    def check_lunch_time(self):
        # проверяем закончился ли обед
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
        # студент отвечает на вопрос
        return question.get_word_by_preferences(self.gender)

    def set_status(self, status):
        # устанавливаем статус студента
        self.status = status


class ExamManager:
    def __init__(self):
        self.professors = []
        self.students = []
        self.question_bank = []
        self.manager = mp.Manager()  # для создания разделяемых объектов между процессами

        #! очередь студентов теперь будет разделяемым объектом
        #! НЕ используем queue.Queue() здесь, так как она не работает между процессами
        self.student_queue = self.manager.Queue()

        self.results_dict = self.manager.dict()
        self.professors_stats = self.manager.dict()
        self.lock = mp.Lock()
        self.start_time = 0
        # Добавляем флаг для завершения процесса отображения
        self.display_finished = self.manager.Event()
        
        # ANSI escape codes
        self.CLEAR_SCREEN = '\033[2J'
        self.MOVE_CURSOR_HOME = '\033[H'
        self.HIDE_CURSOR = '\033[?25l'
        self.SHOW_CURSOR = '\033[?25h'

    def clear_screen(self):
        """Clear the screen and move cursor to home position"""
        print(self.CLEAR_SCREEN + self.MOVE_CURSOR_HOME, end='')

    def hide_cursor(self):
        """Hide the cursor"""
        print(self.HIDE_CURSOR, end='')

    def show_cursor(self):
        """Show the cursor"""
        print(self.SHOW_CURSOR, end='')

    #* функции для работы с файлами
    def loading_data(self):
      try:
        self.loading_professors_from_file("professors.txt")
        self.loading_students_from_file("students.txt")
        self.loading_questions_from_file("questions.txt")

        # Заполняем очередь студентов
        for student in self.students:
            self.student_queue.put(student)

        # Инициализируем статистику экзаменаторов
        for professor in self.professors:
            self.professors_stats[professor.name] = {
                "total_students": 0,
                "failed_students": 0,
                "текущий студент": "-",
                "working_time": 0
            }

        print(f"Данные успешно загружены:")
        print(f"- Экзаменаторов: {len(self.professors)}")
        print(f"- Студентов: {len(self.students)}")
        print(f"- Вопросов: {len(self.question_bank)}")
      except Exception as e:
        print(f"Ошибка при загрузке данных: {str(e)}")
    
    def loading_professors_from_file(self, filename):
        try:
            with open('professors.txt', 'r') as file:
                professors_names = []
                for line in file:
                    name = line.strip()
                    if name:  # Проверяем, что строка не пустая
                        professors_names.append(name)
                        
            self.professors = [Professor(name, [])
                               for name in professors_names]

            print(f"Загружено {len(self.professors)} экзаменаторов из {filename}")

        except FileNotFoundError:
            print(f"Файл {filename} не найден")
            raise

    def loading_students_from_file(self, filename):
        try:
            with open('students.txt', 'r') as file:
                students_data = []
                for line in file:
                    line = line.strip()
                    parts = line.split()  # Split by whitespace instead of comma
                    if len(parts) >= 2:  # Make sure we have both name and gender
                        name = parts[0].strip()
                        gender = parts[1].strip()
                        # Пропускаем строки, которые выглядят как заголовки или примеры
                        if name.lower() == "студент" or name.lower() == "пример":
                            continue
                        students_data.append((name, gender))
        
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

    @staticmethod
    def professors_process(professor_name, professors, student_queue, results_dict, professors_stats, lock, start_time, question_bank):
        # находим экзаменатора по имени
        professor = next(p for p in professors if p.name == professor_name)
        process_start_time = time.time()

        while True:
            # закончился ли обед?
            if professor.check_lunch_time():
                with lock:
                    professors_stats[professor.name]['текущий студент'] = '-'
                    
            # если обед, пропускаем итерацию
            if professor.is_on_lunch:
                time.sleep(0.5)
                continue
                
            try:
                student = student_queue.get_nowait()
            except queue.Empty:
                break
            
            # обнова инфы о текущем студенте
            with lock:
                professor.current_student = student
                professors_stats[professor.name] = {
                    "total_students": professor.total_students,
                    "failed_students": professor.failed_students,
                    "текущий студент": student.name,
                    "working_time": round(time.time() - start_time, 1)
                }

            # проверяем нужен ли обед   
            current_time = time.time() - process_start_time
            if professor.need_lunch(current_time):
                # проводим экзамен текущего студента перед обедом
                exam_result = ExamManager.conduct_exam(professor, student, question_bank)

                with lock:
                    student.set_status(exam_result)
                    results_dict[student.name] = exam_result
                    if exam_result == "Провалил":
                        professor.failed_students += 1
                    professor.total_students += 1
                    professors_stats[professor.name] = {
                        "total_students": professor.total_students,
                        "failed_students": professor.failed_students,
                        "текущий студент": "-",
                        "working_time": round(time.time() - start_time, 1)
                    }
                    
                # профессор идет на обед
                lunch_time = professor.go_to_lunch()
                time.sleep(lunch_time)

                # после обеда обновляем время начала экзамена
                process_start_time = time.time()
                continue

            # проводим экзамен
            exam_time = professor.calculate_exam_time()
            time.sleep(exam_time)  # Симуляция времени экзамена
            exam_result = ExamManager.conduct_exam(professor, student, question_bank)

            # обновляем статистику экзаменатора и результаты студента
            with lock:
                student.set_status(exam_result)
                results_dict[student.name] = exam_result
                if exam_result == "Провалил":
                    professor.failed_students += 1
                professor.total_students += 1
                professors_stats[professor.name] = {
                    "total_students": professor.total_students,
                    "failed_students": professor.failed_students,
                    "текущий студент": "-",
                    "working_time": round(time.time() - start_time, 1)
                }

        # завершение работы экзаменатора
        with lock:
            professors_stats[professor.name] = {
                "total_students": professor.total_students,
                "failed_students": professor.failed_students,
                "текущий студент": "-",
                "working_time": round(time.time() - start_time, 1)
            }

    @staticmethod
    def display_statistics(results_dict, student_queue, professors_stats, start_time, students, lock, display_finished):
        #* отображение текущего состояния экзамена
        while not display_finished.is_set():
            try:
                with lock:
                    # Очищаем экран более агрессивно
                    print('\033[2J\033[H\033[3J', end='', flush=True)
                    # Дополнительно очищаем буфер вывода
                    sys.stdout.flush()
                    
                    # таблица студентов
                    students_data = []
                    for student_name, status in results_dict.items():
                        students_data.append([student_name, status])
                    
                    # добавляем студентов которые в очереди 
                    remaining = 0
                    # Создаем временную копию очереди для подсчета
                    temp_queue = queue.Queue()
                    while not student_queue.empty():
                        student = student_queue.get()
                        students_data.append([student.name, student.status])
                        temp_queue.put(student)
                        remaining += 1
                    # Восстанавливаем очередь
                    while not temp_queue.empty():
                        student_queue.put(temp_queue.get())
                    
                    # время с начала экзамена
                    working_time = round(time.time() - start_time, 1)
                    
                    # таблица экзаменаторов
                    professors_stats_data = []
                    for professor_name, professor_stats in professors_stats.items():
                        professors_stats_data.append([professor_name, professor_stats['total_students'], professor_stats['failed_students'], professor_stats['текущий студент'], round(professor_stats['working_time'], 1)])
                        
                    # выводим таблицу
                    print("\n===== СТАТУС ЭКЗАМЕНА =====")
                    print(f"Время с начала экзамена: {working_time} секунд")
                    print(f"Осталось студентов в очереди: {remaining} из {len(students)}")
                    
                    print("\n----- Экзаменаторы -----")
                    print(tabulate(professors_stats_data, 
                                  headers=["Экзаменатор", "Текущий студент", "Всего студентов", "Завалил", "Время работы"],
                                  tablefmt="grid"))
                    
                    print("\n----- Студенты -----")
                    # Сортируем студентов по статусу
                    students_table = []
                    for student_name, status in results_dict.items():
                        students_table.append([student_name, status])
                    
                    # Добавляем студентов в очереди
                    temp_queue = queue.Queue()
                    while not student_queue.empty():
                        student = student_queue.get()
                        students_table.append([student.name, student.status])
                        temp_queue.put(student)
                    # Восстанавливаем очередь
                    while not temp_queue.empty():
                        student_queue.put(temp_queue.get())
                        
                    # сортируем по статусу, сначала "Сдал", затем "Провалил"
                    students_table.sort(key=lambda x: (x[1] == "Сдал", x[1] == "Провалил"))
                    
                    # выводим таблицу
                    print(tabulate(students_table, 
                                  headers=["Студент", "Статус"],
                                  tablefmt="grid"))
                    
                    # проверяем завершен ли экзамен
                    if not student_queue.empty():
                        time.sleep(1)
                    else:
                        # Если очередь пуста, устанавливаем флаг завершения
                        display_finished.set()
                        break
                        
                    # обновляем статус каждую секунду
                    time.sleep(1)
            except BrokenPipeError:
                break
            except Exception as e:
                print(f"Error in display_statistics: {e}")
                break

    def run_exam(self):
        # загружаем данные 
        self.loading_data()

        # запоминаем время начала экзамена
        self.start_time = time.time()
        
        # запускаем процессы экзаменаторов
        processes = []
        for professor in self.professors:
            process = mp.Process(target=self.professors_process, 
                               args=(professor.name, self.professors, self.student_queue, self.results_dict, 
                                     self.professors_stats, self.lock, self.start_time, self.question_bank))
            processes.append(process)
            process.start()
            
        #  процесс отображения статистики
        display_process = mp.Process(target=self.display_statistics,
                                   args=(self.results_dict, self.student_queue, self.professors_stats, 
                                         self.start_time, self.students, self.lock, self.display_finished))
        display_process.start()
        
        # ждем завершения всех процессов
        for process in processes:
            process.join()
            
        # Устанавливаем флаг завершения для процесса отображения
        self.display_finished.set()
        
        # Ждем завершения процесса отображения
        display_process.join(timeout=2)  # Даем 2 секунды на завершение
        
        # Если процесс отображения все еще работает, завершаем его принудительно
        if display_process.is_alive():
            display_process.terminate()
            display_process.join()

        # выводим итоговые результаты
        self.display_final_results()

    def display_final_results(self):
        # очищаем консоль и перемещаем курсор
        print('\033[2J\033[H', end='')

        # таблица студентов
        students_data = []
        for student_name, status in self.results_dict.items():
            students_data.append([student_name, status])

        # сортируем по статусу: сначала "Сдал", затем "Провалил"
        students_data.sort(key=lambda x: (x[1] == "Сдал", x[1] == "Провалил"))

        print("\n----- Итоговые результаты студентов -----")
        if students_data:
            print(tabulate(students_data, 
                          headers=["Студент", "Статус"],
                          tablefmt="grid",
                          colalign=("left", "center")))
        else:
            print("Нет обработанных студентов")

        # таблица экзаменаторов
        professors_stats = []
        for professor_name, professor_stats in self.professors_stats.items():
            # Убираем пол из имени профессора
            clean_name = professor_name.split()[0]
            professors_stats.append([
                clean_name,
                professor_stats['total_students'],
                professor_stats['failed_students'],
                round(professor_stats['working_time'], 1)
            ])

        # Сортируем профессоров по количеству проваленных студентов (от меньшего к большему)
        professors_stats.sort(key=lambda x: x[2])

        print("\n----- Итоговые результаты экзаменаторов -----")
        if professors_stats:
            print(tabulate(professors_stats, 
                          headers=["Экзаменатор", "Всего студентов", "Завалил", "Время работы"],
                          tablefmt="grid",
                          colalign=("left", "center", "center", "center")))
        else:
            print("Нет данных об экзаменаторах")

        # общая статистика
        passed = sum(1 for status in self.results_dict.values() if status == "Сдал")
        failed = sum(1 for status in self.results_dict.values() if status == "Провалил")
        
        print(f"\nВсего студентов: {len(self.students)}")
        print(f"Сдали: {passed} ({(passed/len(self.students)*100 if len(self.students) > 0 else 0):.1f}%)")
        print(f"Провалили: {failed} ({(failed/len(self.students)*100 if len(self.students) > 0 else 0):.1f}%)")
        print(f"Общее время экзамена: {time.time() - self.start_time:.1f} секунд")
        
        # Добавляем запрошенную информацию
        print("\n----- Дополнительная информация -----")
        print(f"Время с момента начала экзамена и до момента его завершения: {time.time() - self.start_time:.2f}")
        
        # Находим лучших студентов (тех, кто сдал)
        best_students = [name for name, status in self.results_dict.items() if status == "Сдал"]
        if best_students:
            print(f"Имена лучших студентов: {best_students[0]}")  # Берем только первого
        else:
            print("Имена лучших студентов: нет данных")
            
        # Находим лучших экзаменаторов (с наименьшим количеством проваленных студентов)
        if professors_stats:
            best_professors = [p[0] for p in professors_stats[:2]]  # Берем двух лучших
            print(f"Имена лучших экзаменаторов: {', '.join(best_professors)}")
        else:
            print("Имена лучших экзаменаторов: нет данных")
            
        # Находим студентов, которые провалили
        failed_students = [name for name, status in self.results_dict.items() if status == "Провалил"]
        if failed_students:
            print(f"Имена студентов, которых после экзамена отчислят: {failed_students[0]}")  # Берем только первого
        else:
            print("Имена студентов, которых после экзамена отчислят: нет данных")
            
        # Определяем успешность экзамена (сдало больше 85% студентов)
        success_rate = (passed / len(self.students) * 100) if len(self.students) > 0 else 0
        print(f"Вывод: {'экзамен удался' if success_rate > 85 else 'экзамен не удался'}")

    @staticmethod
    def conduct_exam(professor, student, question_bank):
        # выбираем 3 случайных вопроса
        questions = professor.ask_question(question_bank, 3)
        correct_answers = 0
        incorrect_answers = 0
        
        # проводим экзамен
        for question in questions:
            student_answer = student.answer_question(question)
            # проверяем ответ студента  
            if professor.evaluate_question(student_answer, question):   
                correct_answers += 1
            else:
                incorrect_answers += 1
        
        # с вероятностью 1/3 профессор задает дополнительный вопрос 
        while random.random() < 1/3:
            # дополнительный вопрос
            extra_question = random.choice(question_bank)
            student_answer = student.answer_question(extra_question)
            # проверяем ответ студента  
            if professor.evaluate_question(student_answer, extra_question):   
                correct_answers += 1
            else:
                incorrect_answers += 1
        
        # профессор принимает решение
        exam_result = professor.decide_exam_result(correct_answers, incorrect_answers)
        return exam_result

def main():
    # создаем менеджера экзамена
    exam_manager = ExamManager()
    
    # запускаем экзамен
    exam_manager.run_exam()


if __name__ == "__main__":
    main()