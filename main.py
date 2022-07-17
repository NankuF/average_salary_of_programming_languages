import collections

import environs
import requests
import terminaltables

HEADERS = {'User-Agent': '(fireloki87@gmail.com)'}


def get_dictionaries() -> dict:
    """
    Получает словари используемые в API Headhunter.

    :return: словари используемые в API Headhunter.
    """
    url = 'https://api.hh.ru/dictionaries'
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def predict_rub_salary(salary_from: int, salary_to: int, currency: str, currencies: list) -> float:
    """
    Рассчитывает зарплату в рублях.

    :param currencies: словарь валют для перерасчета в рубль.
    :param currency: текущая валюта.
    :param salary_from: зарплата от.
    :param salary_to: зарплата до.
    :return: зарплата в рублях.
    """

    if currency not in ['RUR', 'rub']:
        for cur in currencies:
            if currency == cur['code']:
                if salary_from:
                    salary_from //= cur['rate']
                if salary_to:
                    salary_to //= cur['rate']
    if salary_from and salary_to:
        return (salary_from + salary_to) / 2
    if salary_to:
        return salary_to * 1.2
    if salary_from:
        return salary_from * 0.8


def get_hh_location_id(name: str) -> str:
    """
    Получает название региона или города.
    Пример №1: Красноярский край
    Пример №2: Новосибирск

    :param name: название региона или города.
    :return: id региона или города.
    """

    url = 'https://api.hh.ru/areas'
    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()

    for country in resp.json():
        for region in country['areas']:
            if region['name'].lower() == name.lower():
                return region['id']
            else:
                for city in region['areas']:
                    if name.lower() == city['name'].lower():
                        return city['id']
    raise NameError(f'{get_hh_location_id.__name__}: Город не найден.')


def get_hh_professional_role(name: str) -> str:
    """
    Получает строку идентификаторов специализации.

    :param name: название специализации.
    :return: строка идентификаторов специализации.
    """
    url = 'https://api.hh.ru/professional_roles'

    resp = requests.get(url, headers=HEADERS)
    resp.raise_for_status()
    professional_roles = resp.json()
    ids = []
    for category in professional_roles['categories']:
        for role in category['roles']:
            if name.lower() in role['name'].lower():
                ids.append(role['id'])
    return ','.join(set(ids))


def get_hh_avg_salary(vacancy: str, location: str, secret_key: str = None) -> dict:
    """
    Рассчитывает среднюю зарплату для вакансий на Headhunter.

    :param secret_key: секретный ключ к API.
    :param vacancy: название вакансии.
    :param location: город или регион.
    :return: словарь со средней зарплатой.
    """
    payload = {'text': vacancy,
               'area': get_hh_location_id(name=location),
               'period': 30,
               'professional_role': get_hh_professional_role('программист'),
               'only_with_salary': False,
               'page': 0,
               'search_field': {'name': 'в названии вакансии'},
               'per_page': 100,
               }

    base_url = 'https://api.hh.ru/'
    search_vacancies_url = f'{base_url}vacancies'

    with requests.Session() as session:
        session.headers.update(HEADERS)
        session.params = payload
        collected_vacancies = []
        while True:
            resp = session.get(search_vacancies_url)
            resp.raise_for_status()
            vacancies = resp.json()
            if vacancies['page'] >= vacancies['pages']:
                break

            collected_vacancies.extend(vacancies['items'])
            payload['page'] += 1

    average_salary = 0
    if collected_vacancies:
        currencies = get_dictionaries()['currency']
        vacancies_with_salary = [vacancy for vacancy in collected_vacancies if vacancy['salary']]
        predict_salary = []
        for vacancy in vacancies_with_salary:
            salary_from = vacancy['salary']['from']
            salary_to = vacancy['salary']['to']
            currency = vacancy['salary']['currency']
            predict_salary.append(predict_rub_salary(salary_from, salary_to, currency, currencies))
        if vacancies_with_salary:
            average_salary = sum(predict_salary) / len(vacancies_with_salary)

    return {
        'vacancies_found': vacancies['found'],
        'vacancies_processed': len(vacancies_with_salary) if collected_vacancies else 0,
        'average_salary': int(average_salary),
    }


def get_superjob_avg_salary(vacancy: str, location: str, secret_key: str) -> dict:
    """
    Рассчитывает среднюю зарплату для вакансий на Superjob.

    :param secret_key: секретный ключ к API.
    :param vacancy: название вакансии.
    :param location: город или регион.
    :return: словарь со средней зарплатой.
    """

    headers = {'X-Api-App-Id': secret_key}

    payload = {'town': location,
               'keywords[0][srws]': 1,
               'keywords[0][skwc]': 'and',
               'keywords[0][keys]': vacancy,
               'no_agreement': 0,
               'period': 30,
               'count': 100,
               'page': 0,
               }

    base_url = 'https://api.superjob.ru/2.0/'
    search_vacancies_url = f'{base_url}vacancies'

    collected_vacancies = []
    vacancies_count = 0
    cycle = True
    with requests.Session() as session:
        session.headers.update(headers)
        session.params = payload
        while cycle:
            resp = session.get(search_vacancies_url)
            resp.raise_for_status()
            vacancies = resp.json()
            cycle = vacancies['more']
            vacancies_count = vacancies['total']
            collected_vacancies.extend(vacancies['objects'])
            payload['page'] += 1

    average_salary = 0
    if collected_vacancies:
        currencies = get_dictionaries()['currency']
        vacancies_with_salary = [vacancy for vacancy in collected_vacancies if
                                 vacancy['payment_from'] or vacancy['payment_to']]
        predict_salary = []
        for vacancy in vacancies_with_salary:
            salary_from = vacancy['payment_from']
            salary_to = vacancy['payment_to']
            currency = vacancy['currency']
            predict_salary.append(predict_rub_salary(salary_from, salary_to, currency, currencies))
        if vacancies_with_salary:
            average_salary = sum(predict_salary) / len(vacancies_with_salary)

    return {
        'vacancies_found': vacancies_count,
        'vacancies_processed': len(vacancies_with_salary) if collected_vacancies else 0,
        'average_salary': int(average_salary),
    }


def main():
    """
    Отображает результаты расчета средней зарплаты по языкам программирования в табличном виде в терминале.
    Т.к superjob не поддерживает выдачу вакансий по регионам, следует указывать только город.
    """
    env = environs.Env()
    env.read_env()
    secret_key = env.str('SUPERJOB_SECRET_KEY')

    popular_languages = [
        'JavaScript',
        'Java',
        'Python',
        'Ruby',
        'PHP',
        'C++',
        'C#',
        'C',
        'Go',
    ]

    SearchFunction = collections.namedtuple('SearchFunction', ['func', 'name'])
    headhunter = SearchFunction(func=get_hh_avg_salary, name='Headhunter')
    superjob = SearchFunction(func=get_superjob_avg_salary, name='Superjob')

    funcs = [headhunter, superjob]

    language_salaries = {}
    for func in funcs:
        for language in popular_languages:
            language_salaries[language] = func.func(vacancy=f'Программист {language}',
                                                    location='Москва',
                                                    secret_key=secret_key)

        table = [['Язык программирования', 'Вакансий найдено', 'Вакансий обработано', 'Средняя зарплата']]
        final_language_info = []
        for language, language_info in language_salaries.items():
            final_language_info.append(language)
            final_language_info.extend(language_info.values())
            table.append(final_language_info)
            final_language_info = []

        table = terminaltables.SingleTable(table, func.name)

        print(table.table)


if __name__ == '__main__':
    main()
