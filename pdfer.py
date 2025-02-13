import importlib
import os
import re
import shutil
import sys
import textwrap
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import inquirer
    import PyPDF2


def is_int(s: str) -> bool:
    """Проверяет, является ли строка `s` целым числом"""
    return bool(re.match(r'^-?\d+$', s))


def clear():
    """Очищает консоль"""
    os.system('cls' if os.name == 'nt' else 'clear')


def import_or_install_module(module_name: str):
    """Импортирует модуль и предустанавливает его, если он не установлен"""
    try:
        globals()[module_name.replace('-', '_')] = importlib.import_module(module_name.replace('-', '_'))
    except ModuleNotFoundError:
        print(f'{module_name} не установлен в Python. Установка...')
        if os.name == 'nt':
            os.system(f'py -m pip install {module_name} > {os.devnull} 2>&1')
        else:
            os.system(f'python3 -m pip install --break-system-packages {module_name} > {os.devnull} 2>&1')
        globals()[module_name.replace('-', '_')] = importlib.import_module(module_name.replace('-', '_'))


clear()
import_or_install_module('inquirer')
from inquirer.errors import ValidationError  # noqa: E402

import_or_install_module('prompt_toolkit')
from prompt_toolkit import PromptSession  # noqa: E402
from prompt_toolkit.completion import WordCompleter  # noqa: E402
from prompt_toolkit.validation import Validator  # noqa: E402

import_or_install_module('rich')
from rich.console import Console  # noqa: E402

import_or_install_module('PyPDF2')

console = Console()
session = PromptSession()


class PDFer:
    """Класс, формирующий основной функционал программы"""

    @staticmethod
    def extract_page_range(input_pdf: str, start_page: int, end_page: int = -1, output_pdf: str = '') -> str:
        """Извлекает страницы из PDF-файла `input_pdf` в диапазоне от `start_page`
        до `end_page` включительно и сохраняет их в новый PDF-файл\n
        Если `end_page` не указана, то извлекается только одна страница `start_page`"""
        with open(input_pdf, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            writer = PyPDF2.PdfWriter()

            if end_page == -1:
                end_page = start_page

            order, shift = (1, 0) if start_page <= end_page else (-1, -2)
            start_page = max(0, start_page - 1)
            end_page = min(end_page, len(reader.pages)) + shift
            for page_num in range(start_page, end_page, order):
                writer.add_page(reader.pages[page_num])

        output_pdf = (output_pdf or input_pdf.removesuffix('.pdf')) + (
            (f'_{start_page + 1}' if start_page == end_page else f'_{start_page + 1}-{end_page}') + ' [PDFer].pdf'
        )
        with open(output_pdf, 'wb') as output_file:
            writer.write(output_file)
        return output_pdf

    @staticmethod
    def parse_page_ranges(page_ranges_str: str):
        """Парсит строку `page_ranges_str` с диапазонами страниц в формате '1-5, 8, 11-13'"""
        page_ranges = []
        for part in page_ranges_str.replace(' ', '').split(','):
            if '-' in part:
                start, end = map(int, part.split('-'))
                page_ranges.append([start, end])
            else:
                page_ranges.append([int(part)])
        return page_ranges

    @staticmethod
    def merge_pdfs(input_pdfs: list[str], output_pdf: str):
        """Склеивает несколько PDF-файлов `input_pdfs` в один PDF-файл `output_pdf`"""
        writer = PyPDF2.PdfWriter()

        for input_pdf in input_pdfs:
            with open(input_pdf, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page_num in range(len(reader.pages)):
                    writer.add_page(reader.pages[page_num])

        with open(output_pdf, 'wb') as output_file:
            writer.write(output_file)


class Validators:
    """Класс, содержащий валидаторы для полей ввода"""

    @staticmethod
    def is_to_exit(x: str) -> bool:
        return x in COMMANDS['exit']

    int_ = Validator.from_callable(lambda x: is_int(x) or Validators.is_to_exit(x), error_message='Введи только число!')
    pdf = lambda pass_enter: Validator.from_callable(
        lambda x: x.endswith('.pdf')
        or x.endswith('.pdf"')
        or Validators.is_to_exit(x)
        or (x == '' if pass_enter else False),
        error_message='Файл должен быть PDF-файлом!',
    )
    range_ = Validator.from_callable(
        lambda x: all([re.match(r'^\s*\d+(\s*-\s*\d+)?\s*$', i) for i in x.replace(' ', '').split(',')])
        or Validators.is_to_exit(x),
        error_message='Введи через запятую только диапазоны через дефис и числа!',
    )

    @staticmethod
    def menu(_, current):
        if str(current) == ' ':
            raise ValidationError('', reason='Я всего лишь разделитель... Не трогай меня :)')
        return True


class Interface:
    """Класс, формирующий интерфейс программы"""

    last_option = None

    @staticmethod
    def draw_header(full=False, compact=False):
        """Очищает консоль и отрисовывает хедер программы в консоли"""
        columns = shutil.get_terminal_size().columns
        clear()
        console.print('[blue]┌' + '─' * (columns - 2) + '┐')
        if not compact:
            console.print('[blue]│' + ' ' * (columns - 2) + '│')
        console.print('[blue]│[/blue][red]' + 'PDFer'.center(columns - 2) + '[/red][blue]│')
        if not compact:
            if full:
                console.print('[blue]│[/blue]' + 'c любовью от snowlue 💙'.center(columns - 3) + '[blue]│')
                console.print('[blue]│' + ' ' * (columns - 2) + '│')
                console.print(
                    '[blue]│[/blue]'
                    + 'Никогда ещё работа с PDF не была настолько простой и быстрой!'.center(columns - 2)
                    + '[blue]│'
                )
            console.print('[blue]│' + ' ' * (columns - 2) + '│')
        console.print('[blue]└' + '─' * (columns - 2) + '┘' + ('' if compact else '\n'))

    @staticmethod
    def override_keyboard_interrupt(func):
        """Декоратор для перехвата KeyboardInterrupt"""

        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except KeyboardInterrupt:
                return Interface.start()

        return wrapper

    @staticmethod
    def start():
        """Запускает интерфейс программы"""
        Interface.draw_header(full=True)
        questions = [
            inquirer.List(
                'choice',
                message='Выбери действие',
                choices=MENU,
                default=Interface.last_option,
                validate=Validators.menu,  # type: ignore
                carousel=True,
            )
        ]
        answers = inquirer.prompt(questions)
        try:
            Interface.last_option = answers['choice']
            ACTIONS_MATRIX[answers['choice']]['action']()
        except TypeError:
            return Interface.draw_exit()

    @staticmethod
    def get_pdf_file(pass_enter: bool = False, prompt_text: str = '', completer_list: set = set()) -> str | None:
        """Интерфейс для получения имени PDF-файла\n
        При `pass_enter = True` валидатор пропускает пустую строку (в случае если был нажат Enter)"""
        files = (
            list(completer_list)
            or list(set(file for file in os.listdir() if os.path.isfile(file) and file.endswith('.pdf')))
            or [
                'в запущенной папке нет PDF-файлов',
                'указывай полный путь',
            ]
        )
        completer = WordCompleter(files)
        input_pdf = session.prompt(
            prompt_text or 'Введи имя входного PDF-файла: ',
            completer=completer,
            validator=Validators.pdf(pass_enter),
            mouse_support=True,
        )

        if input_pdf in COMMANDS['exit']:
            return 'exit' if pass_enter else None
        return input_pdf.removeprefix('"').removesuffix('"')

    @override_keyboard_interrupt
    @staticmethod
    def extract_many():
        """Интерфейс для извлечения набора страниц из PDF-файла"""
        Interface.draw_header()
        input_pdf = Interface.get_pdf_file()
        if not input_pdf:
            return Interface.start()
        pages = session.prompt('Введи страницы: ', completer=WordCompleter([]), validator=Validators.range_)
        if pages in COMMANDS['exit']:
            return Interface.start()
        try:
            os.mkdir('temp')
        except FileExistsError:
            shutil.rmtree('temp')
            os.mkdir('temp')

        files: list[str] = []
        for page_range in PDFer.parse_page_ranges(pages):
            files.append(
                PDFer.extract_page_range(input_pdf, *page_range, output_pdf=f'temp/{os.path.basename(input_pdf)}')
            )
        pages = ','.join([file.rsplit('_')[1].split(' ')[0] for file in files])

        file_name = f'{input_pdf.removesuffix(".pdf")}_{pages} [PDFer].pdf'
        PDFer.merge_pdfs(files, file_name)
        shutil.rmtree('temp')
        file_name = basename if (basename := os.path.basename(file_name)) in os.listdir() else file_name
        console.print(f'[on dark_green]Диапазоны страниц успешно извлечены в файл {file_name}![/on dark_green]')
        input()
        Interface.start()

    @override_keyboard_interrupt
    @staticmethod
    def extract_range():
        """Интерфейс для извлечения одного диапазона страниц из PDF-файла"""
        Interface.draw_header()
        input_pdf = Interface.get_pdf_file()
        if not input_pdf:
            return Interface.start()
        start_page = session.prompt(
            'Введи начальную страницу: ', completer=WordCompleter([]), validator=Validators.int_
        )
        if start_page in COMMANDS['exit']:
            return Interface.start()
        else:
            start_page = int(start_page)
        end_page = session.prompt('Введи конечную страницу: ', completer=WordCompleter([]), validator=Validators.int_)
        if end_page in COMMANDS['exit']:
            return Interface.start()
        else:
            end_page = int(end_page)

        file_name = PDFer.extract_page_range(input_pdf, start_page, end_page)
        file_name = basename if (basename := os.path.basename(file_name)) in os.listdir() else file_name
        console.print(f'[on dark_green]Диапазон страниц успешно извлечён в файл {file_name}![/on dark_green]')
        input()
        Interface.start()

    @override_keyboard_interrupt
    @staticmethod
    def extract_single():
        """Интерфейс для извлечения одной страницы из PDF-файла"""
        Interface.draw_header()
        input_pdf = Interface.get_pdf_file()
        if not input_pdf:
            return Interface.start()

        page_number = session.prompt('Введи страницу: ', completer=WordCompleter([]), validator=Validators.int_)
        if page_number in COMMANDS['exit']:
            return Interface.start()
        else:
            page_number = int(page_number)

        file_name = PDFer.extract_page_range(input_pdf, page_number)
        file_name = basename if (basename := os.path.basename(file_name)) in os.listdir() else file_name
        console.print(f'[on dark_green]Страница успешно извлечена в файл {file_name}![/on dark_green]')
        input()
        Interface.start()

    @override_keyboard_interrupt
    @staticmethod
    def merge(not_enough: bool = False):
        """Интерфейс для склеивания нескольких PDF-файлов в один"""
        Interface.draw_header()
        input_pdfs = []
        if not_enough:
            console.print('[on dark_red]Недостаточно PDF-файлов для склеивания![/on dark_red]', end='\n\n')
            not_enough = False
        while True:
            input_pdf = Interface.get_pdf_file(
                True, f'Введи имя {len(input_pdfs) + 1}-го PDF-файла для склеивания: ', set(input_pdfs)
            )
            if input_pdf == 'exit':
                return Interface.start()
            if input_pdf:
                input_pdfs.append(input_pdf)
                continue
            break

        if len(input_pdfs) < 2:
            return merge(True)

        file_name = Interface.get_pdf_file(
            prompt_text='Введи имя выходного PDF-файла: ', completer_list=set(input_pdfs)
        )
        if not file_name:
            return Interface.start()

        if file_name == os.path.basename(file_name):
            base_path = os.path.dirname(input_pdfs[0])
            if all(os.path.dirname(file) == base_path for file in input_pdfs[1:]):
                file_name = os.path.join(base_path, file_name)
        file_name = file_name.removesuffix('.pdf') + ' [PDFer].pdf'
        PDFer.merge_pdfs(input_pdfs, file_name)
        console.print(f'[on dark_green]PDF-файлы успешно склеены в файл {file_name}![/on dark_green]')
        input()
        Interface.start()

    @override_keyboard_interrupt
    @staticmethod
    def draw_help():
        """Отрисовывает помощь по программе"""
        columns = shutil.get_terminal_size().columns

        for action in ACTIONS_MATRIX.keys():
            help_info = ACTIONS_MATRIX[action]['help']
            Interface.draw_header(compact=True)
            console.print(f'[b]> {action}[/b]')
            for paragraph in help_info:
                print(
                    ''.join(
                        [
                            textwrap.indent(row.ljust(columns - 5), '  │  ')
                            for row in textwrap.wrap(paragraph, columns - 5)
                        ]
                    ),
                    end='\n\n' if paragraph.endswith('\n') else '\n',
                )
            print()
            if ACTIONS_MATRIX[action]['flags']['help_about_exit']:
                text = 'Для возврата в главное меню на любом этапе напишите ' + ', '.join(COMMANDS['exit'])
                print(
                    ''.join(
                        [textwrap.indent(row.ljust(columns - 5), '  │  ') for row in textwrap.wrap(text, columns - 5)]
                    )
                )
                print()
            console.print('Нажми [i]Enter[/i] для продолжения или [i]Ctrl-C[/i] для выхода из справки...', end='')
            input()
        Interface.start()

    @override_keyboard_interrupt
    @staticmethod
    def draw_about():
        """Отрисовывает информацию о разработчике"""
        empty_line = lambda: console.print('[gold1]║' + ' ' * (columns - 2) + '║')

        columns = shutil.get_terminal_size().columns
        clear()

        console.print('[gold1]╔' + '═' * (columns - 2) + '╗')
        empty_line()
        console.print('[gold1]║[/gold1][red3]' + 'PDFer'.center(columns - 2) + '[/red3][gold1]║')
        console.print('[gold1]║[/gold1]' + 'c любовью от snowlue 💙'.center(columns - 3) + '[gold1]║')
        empty_line()
        raw, styled = (
            'Никогда ещё работа с PDF не была настолько простой и быстрой!',
            'Никогда ещё работа с PDF не была настолько [u]простой[/u] и [u]быстрой[/u]!',
        )
        console.print('[gold1]║[/gold1]' + raw.center(columns - 2).replace(raw, styled) + '[gold1]║')
        empty_line()
        console.print('[gold1]╠' + '═' * (columns - 2) + '╣')
        empty_line()
        empty_line()
        raw, styled = 'Разработчик:  Павел Овчинников', '[blink]Разработчик:  Павел Овчинников[/blink]'
        console.print('[gold1]║[/gold1]' + raw.center(columns - 2).replace(raw, styled) + '[gold1]║')
        empty_line()

        if os.name == 'nt':
            raw, styled = (
                'VK   |   Telegram   |   GitHub',
                '[dodger_blue2][link=https://vk.com/snowlue]VK[/link][/dodger_blue2]   |   [deep_sky_blue1][link=https://t.me/snowlue]Telegram[/link][/deep_sky_blue1]   |   [link=https://github.com/snowlue][bright_white]GitHub[/bright_white][/link]',
            )
            console.print('[gold1]║[/gold1]' + raw.center(columns - 2).replace(raw, styled) + '[gold1]║')
        else:
            raw, styled = (
                ' VK' + ' ' * 12 + '│' + ' ' * 8 + 'Telegram' + ' ' * 8 + '│' + ' ' * 12 + 'GitHub',
                ' [dodger_blue2]VK[/dodger_blue2]'
                + ' ' * 12 + '│' + ' ' * 8
                + '[deep_sky_blue1]Telegram[/deep_sky_blue1]'
                + ' ' * 8 + '│' + ' ' * 12
                + '[bright_white]GitHub[/bright_white]',
            )
            console.print('[gold1]║[/gold1]' + raw.center(columns - 2).replace(raw, styled) + '[gold1]║')
            links = 'https://vk.com/snowlue  │  https://t.me/snowlue  │  https://github.com/snowlue'
            console.print('[gold1]║[/gold1]' + links.center(columns - 2) + '[gold1]║')

        empty_line()
        empty_line()
        console.print('[gold1]╚' + '═' * (columns - 2) + '╝', end='\n\n')
        raw, styled = (
            f'© {datetime.now().year}, Pavel Ovchinnikov',
            f'[grey66]© {datetime.now().year}, Pavel Ovchinnikov[/grey66]',
        )
        console.print(raw.center(columns).replace(raw, styled), end='')
        input()
        Interface.start()

    @staticmethod
    def draw_exit():
        """Отрисовывает завершение программы"""
        Interface.draw_header()
        console.print('    [u]Жду твоего возвращения![/u] 👋🏼', justify='center')
        sys.exit(0)


class Separator:
    """Класс-разделитель для меню"""

    def __repr__(self):
        return 'Separator'

    def __str__(self):
        return ' '


COMMANDS = {'exit': ['exit', 'выход', 'выйти', 'quit', 'q']}

ACTIONS_MATRIX = {
    ' Извлечь набор страниц из PDF-файла': {
        'action': Interface.extract_many,
        'flags': {'help_about_exit': True},
        'help': [
            'Извлекает сразу нескольких диапазонов и страниц из PDF-файла и сохраняет их в новый.\n',
            'Покрывает все основные случаи использования, т.к. извлекает страницы независимо, например: 1-5, 8, 11-13. Более того, имеется возможность извлекать страницы в обратном порядке, например: 5-1. И в дополнение, страницы можно дублировать: 1, 1, 3-5, 4, 1. Все диапазоны обрабатываются от начальной и до конечной страницы включительно.\n',
            '– Для начала введи название PDF-файла, из которого хочешь извлечь страницы.',
            '– Затем введи диапазоны страниц через запятую.',
        ],
    },
    ' Извлечь один диапазон страниц из PDF-файла': {
        'action': Interface.extract_range,
        'flags': {'help_about_exit': True},
        'help': [
            'Извлекает один диапазон страниц из PDF-файла от начальной и до конечной страницы включительно. Если конечная страница не указана, то извлекается только одна начальная страница.\n',
            '– Для начала введи название PDF-файла, из которого хочешь извлечь страницы.',
            '– Затем введи начальную страницу.',
            '– И в конце введи конечную страницу.',
        ],
    },
    ' Извлечь одну страницу из PDF-файла': {
        'action': Interface.extract_single,
        'flags': {'help_about_exit': True},
        'help': [
            'Извлекает только одну страницу из PDF-файла.\n',
            '– Для начала введи название PDF-файла, из которого хочешь извлечь страницу.',
            '– Затем введи номер страницы, которую хочешь извлечь.',
        ],
    },
    ' Склеить несколько PDF-файлов в один': {
        'action': Interface.merge,
        'flags': {'help_about_exit': True},
        'help': [
            'Склеивает несколько PDF-файлов в один общий. Порядок склеивания определяется введённым списком PDF-файлов. Если во введённом имени выходного файла не указан путь, то новый файл со склеенными PDF создаётся в той же папке, что и все файлы, если они расположены в одном месте — иначе в той же папке, что и этот модуль.\n',
            '– Вводи имена PDF-файлов, которые хочешь склеить, по одному, нажимая Enter после каждого.',
            '– Как только закончишь, нажмите Enter с пустой строкой, ничего не вводя.',
            '– В конце введи имя выходного PDF-файла.',
        ],
    },
    ' Помощь': {
        'action': Interface.draw_help,
        'flags': {'help_about_exit': False},
        'help': ['Выводит эту справку по функционалу.'],
    },
    ' О программе': {
        'action': Interface.draw_about,
        'flags': {'help_about_exit': False},
        'help': ['Выводит информацию о программе и разработчике.'],
    },
    ' Выход': {'action': Interface.draw_exit, 'flags': {'help_about_exit': False}, 'help': ['Завершает PDFer.']},
}

MENU = list(ACTIONS_MATRIX.keys())[:-3] + [Separator()] + list(ACTIONS_MATRIX.keys())[-3:]


def main():
    """Точка входа в программу"""
    if not __loader__:
        Interface.start()
    elif __loader__.name != os.path.basename(__file__).removesuffix('.py'):  # не запущен как модуль через флаг -m
        if len(sys.argv) == 1:  # не запущен через python
            return Interface.start()

    # TODO: здесь через argparse опишу логику для запуска с параметрами командной строки
    # TODO: --extract file.pdf a-b,c,d-f
    # TODO: --merge file1.pdf file2.pdf file3.pdf new_file.pdf
    # TODO: --help, --about


if __name__ == '__main__':
    main()
