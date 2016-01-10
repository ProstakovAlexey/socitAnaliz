#!/usr/bin/python3

__author__ = 'Простаков Алексей'
"""
Программа строит графики скорости выполнения тестовых примеров.

Построение выполняется для ИС и веб-сервисов из конфиграционного
файла. Результат в каталоге Графики, подкаталог с названием ИС.
Каждый веб-сервис на отдельном поле, имя = название теста. Для
построения используется программа gnuplot
"""
import os, glob
from pymongo import MongoClient
import sys
import configparser
import logging
import subprocess
import datetime


# определение констант
gnuplot =r"""
set terminal  png size 600,400 font 'Verdana, 8'
set output '#FILE_NAME#.png'
set title '#TITLE#'
set ylabel "Время выполнения, сек"
set xdata time
set timefmt "%d.%m.%Y %H:%M"
set format x "%d.%m\n%H:%M"
set xlabel "Дата/время"
set grid xtics ytics #y2tics
set key top right
set y2range[0:5]
set y2label "Кол-во ошибок"
set y2tics
set xtic rotate by 90 scale 0 offset character 0,-2
plot 'data.tmp' u 1:4 ti "Ошибки" with impulse axes x1y2,\
'' u 1:3 ti "#SERVICE_NAME#" w li lw 2
"""
logging.basicConfig(filename='web-service_Graph.log', filemode='a', level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s')
showTime = datetime.datetime.now() - datetime.timedelta(days=7)


def printMsg(post):
    print("%s выполнено за %s сек. ошибок %s."
                % (post['name'], post['data']['Итого'], post['errors']))
    if post['errors']:
        logging.error("%s Выполнено за %s ошибок %s."
            % (post['name'], post['data']['Итого'], post['errors']))
    else:
        logging.info("%s Выполнено за %s без ошибок."
            % (post['name'], post['data']['Итого']))


def getDataFile(collection, get):
    res = 1
    get['date'] = { "$gte": showTime }
    fp = open ('data.tmp', 'w')
    result = collection.find(get)
    if result:
        for post in result:
            st = '%s\t%s\t%s' % (post['date'].strftime("%d.%m.%Y %H:%M"), post['data']['Итого'], post['errors'])
            print(st, file=fp)
    else:
        res = 0
    fp.close()
    if res:
        logging.info('Данные для %s %s успешно получены из БД'
            % (get['name'], get['comment']))
        # подстановка в шаблон и построение графика
    else:
        logging.error('Данные для %s %s не содержатся в БД'
            % (get['name'], get['comment']))
    return(res)


def plotGraph(post):
    """ Строит график по времени  для заданного теста"""
    fs = open('gnuplot.tmp', 'w')
    sh = gnuplot.replace("#SERVICE_NAME#", post['name'])
    sh = sh.replace("#FILE_NAME#", dirName + '/' + post['name'])
    sh = sh.replace("#TITLE#", post['comment'])
    print(sh, file=fs)
    fs.close()
    err = subprocess.call(["gnuplot", 'gnuplot.tmp'])
    if err:
        logging.error("При вызове gnuplot возникла ошибка")
    else:
        logging.info("График %s построен успешно" % post['name'])


def readConfig(file="config.ini"):
    '''
    :param file: имя файла конфигурации
    :return: список ИС для тестирования, словарь настроек к БД, кол-во ошибок
    '''
    err = 0
    ISList = list()
    BD = dict()
    if os.access(file, os.F_OK):
        # выполняется если найден конфигурационный файл
        config_str = open(file, encoding='utf-8', mode='r').read()
        # удалить признак кодировки
        config_str = config_str.replace(u'\ufeff', '')
        # чтение конфигурационного файла
        Config = configparser.ConfigParser()
        Config.read_string(config_str)
        sections = Config.sections()
        # читаем все секции
        for section in sections:
            i = Config[section]
            # это секция про ИС, их может быть несколько
            if section.count('IS'):
                IS = dict()
                IS['snd_name'] = i.get('name', fallback='СОЦИНФОРМТЕХ')
                IS['snd_code'] = i.get('mnemonic', fallback='SOCP01711')
                IS['oktmo'] = i.get('OKTMO', fallback='70000000')
                IS['url'] = i.get('URL', fallback='/socportal/')
                IS['adr'] = i.get('address', fallback='')
                IS['port'] = i.get('port', fallback='80')
                IS['servicecode'] = i.get('SERVICE_CODE', fallback='123456789')
                IS['SpravID'] = i.get('SpravID', fallback='1')
                IS['comment'] = i.get('comment', fallback='')
                IS['373'] = i.get('373', fallback='no')
                IS['409'] = i.get('409', fallback='no')
                IS['510'] = i.get('510', fallback='no')
                IS['PGU'] = i.get('PGU', fallback='no')
                IS['1003'] = i.get('1003', fallback='no')
                IS['1004'] = i.get('1004', fallback='no')
                IS['1005'] = i.get('1005', fallback='no')
                IS['1007'] = i.get('1007', fallback='no')
                IS['web'] = i.get('web', fallback='no')
                ISList.append(IS)
            # это про подсоединение к БД
            elif section == 'BD':
                BD['adr'] = i.get('address', fallback='')
                BD['port'] = i.get('port', fallback='27017')
                BD['BD'] = i.get('dataBase', fallback='')
                BD['collection'] = i.get('collection', fallback='')
        # проверим заполнение секции о БД
        if len(BD.keys()) == 0:
            print('В конфигурационном файле отсутствует обязательная секция о БД.')
            err += 1
        else:
            for key in BD.keys():
                if BD[key] == '':
                    print("Параметр %s не должен быть пустой, заполните его в конфигурационном файле %s" % (key, file))
                    err += 1
        # проверим заполнение сведений об ИС
        if len(ISList) == 0:
            print('В конфигурационном файле отсутствует обязательная секция об ИС.')
            err += 1
        else:
            for IS in ISList:
                for key in IS.keys():
                    if IS[key] == '':
                        print("В секции сведение об ИС параметр %s не должен быть пустой, заполните его в конфигурационном файле %s" % (key, file))
                        err += 1
    # нет конфигурационного файла
    else:
        print("Ошибка! Не найден конфигурационный файл")
        err = 1
    return ISList, BD, err


if __name__ == '__main__':
    logging.info("Программа запущена")
    # чтение конфигурационного файла
    ISList, BD, err = readConfig('config.ini')
    if err > 0 or ISList is None or BD is None:
        logging.critical("При чтении конфигурационного файла произошли ошибки. Программа остановлена")
        exit(1)
    else:
        logging.info("Конфигурационный файл прочитан успешно.")
    # очистка папку Графики
    err = subprocess.call(['rm', '-R', 'Графики/'])
    if err:
        logging.error("При очистки папка Графики возникла ошибка.")
    else:
        logging.info("Очищена папка Графики")
        os.mkdir('Графики')
    # соединяемся с БД для записи протокола
    try:
        client = MongoClient(BD['adr'], int(BD['port']))
        db = client[BD['BD']]
        collection = db[BD['collection']]
    except:
        logging.critical("Ошибка при соединении с БД. Программа остановлена")
        Type, Value, Trace = sys.exc_info()
        logging.critical("""Тип ошибки: %s
Текст: %s""" % (Type, Value))
        exit(2)
    logging.info('Успешное соединения с БД')
    # перебираем все ИС из конф. файла
    for IS in ISList:
        logging.info('Обрабатываем ИС: %s' % IS['snd_name'])
        # создаем папку для графиков
        dirName = 'Графики/' + IS['comment']
        os.mkdir(dirName)
        # тест для 373
        if IS['373'] == 'yes':
            get = {
                "name": "Тестирование 373 сервиса",
                "comment": IS['comment'],
            }
            # пробуем получить данные и если успешно, строим график
            if getDataFile(collection, get):
                plotGraph(get)
        # тест для 409
        if IS['409'] == 'yes':
            get = {
                "name": "Тестирование 409 сервиса",
                "comment": IS['comment']
            }
            # пробуем получить данные и если успешно, строим график
            if getDataFile(collection, get):
                plotGraph(get)
        # тест для 510
        if IS['510'] == 'yes':
            get = {
                "name": "Тестирование 510 сервиса",
                "comment": IS['comment']
            }
            # пробуем получить данные и если успешно, строим график
            if getDataFile(collection, get):
                plotGraph(get)
        # тест для ПГУ
        if IS['PGU'] == 'yes':
            get = {
                "name": "Тестирование ПГУ сервиса",
                "comment": IS['comment']
            }
            # пробуем получить данные и если успешно, строим график
            if getDataFile(collection, get):
                plotGraph(get)
        # тест для 1003
        if IS['1003'] == 'yes':
            get = {
                "name": "Тестирование 1003 сервиса",
                "comment": IS['comment']
            }
            # пробуем получить данные и если успешно, строим график
            if getDataFile(collection, get):
                plotGraph(get)
        # для 1004
        if IS['1004'] == 'yes':
            get = {
                "name": "Тестирование 1004 сервиса",
                "comment": IS['comment']
            }
            # пробуем получить данные и если успешно, строим график
            if getDataFile(collection, get):
                plotGraph(get)
        # Тест для 1005
        if IS['1005'] == 'yes':
            get = {
                "name": "Тестирование 1005 сервиса",
                "comment": IS['comment']
            }
            # пробуем получить данные и если успешно, строим график
            if getDataFile(collection, get):
                plotGraph(get)
        # Тест для 1007
        if IS['1007'] == 'yes':
            get = {
                "name": "Тестирование 1007 сервиса",
                "comment": IS['comment']
            }
            # пробуем получить данные и если успешно, строим график
            if getDataFile(collection, get):
                plotGraph(get)

        # тест для веб-интерфейса
        if IS['web'] == 'yes':
            get = {
                "name": "Тестирование веб-интерфейса ТИ",
                "comment": IS['comment']
            }
            # пробуем получить данные и если успешно, строим график
            if getDataFile(collection, get):
                plotGraph(get)
    # закрывает соединения с БД
    client.close()
    # удаляем временные файлы
    subprocess.call(['rm', 'gnuplot.tmp'])
    subprocess.call(['rm', 'data.tmp'])
    logging.info('Программа работу закончила')
    exit(0)
