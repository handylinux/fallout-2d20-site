#!/usr/bin/env python3
"""Export original heavy mod blocks alongside Companion rows for manual review."""
import json
from pathlib import Path
import pymupdf
import weapon_heavy_preview as heavy
import companion_mods_receiver as conv
from weapons2cards import Companion

ROOT = Path(__file__).resolve().parent.parent

def build(source, output):
    comp = Companion()
    prefixes = conv.load(conv.PREFIXES)
    ids = json.loads(heavy.ORDER_FILE.read_text(encoding='utf-8'))
    lines = ['# Сверка модификаций тяжёлого оружия', '',
             'Приоритет для оружия из исходного справочника — его таблица. Ниже приведены исходный текст блока и строки рабочей копии Companion для ручной сверки; это не автоматическое утверждение о различии каждой строки. Переносы и порядок полей в извлечённом тексте могут отличаться от PDF. Исходные данные Companion не изменены.', '',
             '## Подтверждённые и подозрительные расхождения', '',
             '- Пушка робота: оригинал прямо указывает отсутствие поддерживаемых модификаций; в Companion перечислены 17 слотов, однако ни один мод не содержит ID оружия в applies_to_ids. В книге взят оригинал.',
             '- Гатлинг-плазма: в исходном PDF отсутствует. В Companion указан список из 17 слотов, но ни один мод не содержит ID оружия в applies_to_ids. Вместо этого на странице выведены пять модификаций из дампа сайта (страница 351); их сверка с книгами не завершена. Удобная ложа убирает «Отдачу» (6), хотя в базовой карточке это качество не указано — расхождение требует проверки.',
             '- Гатлинг-лазер: оригинал даёт тюнеру бета-волн эффект «Порочный», +1 вес и +19 цену; Companion — «Устойчивый», вес не указан, +30 цена. Остальные строки также следует проверить.',
             '- Миниган Гаусса: оригинал содержит пятиствольный ствол, которого нет в списке слотов рабочей копии Companion.', '',
             '## Сопоставление для проверки', '']
    with pymupdf.open(source) as doc:
        for index, wid in enumerate(ids):
            lines.extend([f'### {wid}', ''])
            if wid in heavy.SOURCE_PAGES:
                source_page = heavy.SOURCE_PAGES[wid]
                page = doc[source_page - 1]
                words = [word for word in page.get_text('words') if 'МОДИФИКАЦИ' in word[4]]
                top = words[0][1] - 5
                text = page.get_text('text', clip=pymupdf.Rect(0, top, page.rect.width, 807)).strip()
                lines.extend([f'**Оригинал, физическая страница {source_page}:**', '', '```', text, '```', ''])
            else:
                lines.extend(['**Оригинал:** оружия в исходном PDF нет.', ''])
            lines.extend(['**Companion (слот; название; префикс; эффекты; вес; цена; перки):**', ''])
            rows = heavy.build_rows(comp, wid, prefixes)
            lines.extend(['- ' + ' | '.join([slot] + values) for slot, values in rows] or ['- Нет строк в списке слотов.'])
            lines.append('')
    Path(output).write_text('\n'.join(lines), encoding='utf-8')

if __name__ == '__main__':
    build(ROOT / 'Справочник оружия.pdf', ROOT / 'docs/weapon-heavy-mods-comparison.md')
