#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
powerarmor_mods_from_helper — моды силовой брони из проекта
`handylinux/Fallout-2d20-helper` в данные Fallout-2d20 Companion.

В Companion (`data/companion/equipment/powerArmor.json`) модов силовой
брони нет — только детали (шлем / нагрудник / наручи / поножи). Моды есть
в helper:
  * `back/src/db/seed/data/mods.ts` — записи `applicableTo: 'powerArmor'`,
    слоты systeme / blindage / amelioration; числа (вес, цена, перки,
    эффекты) — оттуда;
  * `back/src/db/seed/data/itemModCompatibility.ts` —
    `POWER_ARMOR_COMPATIBILITY`: что к какой детали подходит (списки
    собираются из констант — скрипт их раскрывает);
  * `front/src/i18n/locales/en.ts` — английские названия и тексты
    эффектов `mods.effects.pa.*` (для сверки).

Скрипт пишет:
  data/companion/equipment/powerArmor_mods.json
  data/companion/equipment/powerArmor_modCompatibility.json
  data/companion/i18n/ru-RU/data/equipment/armor/powerArmor_mods.json

Русские названия — NAMES_RU, тексты эффектов — EFFECTS_RU (перевод строк
из `en.ts`). Ничего не выдумывается: числа берутся из helper.

Запуск:
    git clone --depth 1 https://github.com/handylinux/Fallout-2d20-helper.git /tmp/helper
    python3 tools/powerarmor_mods_from_helper.py /tmp/helper
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SLOT_RU = {"systeme": "Система", "blindage": "Обшивка",
           "amelioration": "Улучшение"}
PARTS_RU = {"casque": "шлем", "plastron": "нагрудник",
            "brassard": "наручи", "jambiere": "поножи"}
PARTS_EN = {"casque": "Helmet", "plastron": "Chest Piece",
            "brassard": "Arm", "jambiere": "Leg"}
PART_AREAS = {"casque": ["Head"], "plastron": ["Body"],
              "brassard": ["Hand"], "jambiere": ["Leg"]}

# ключ helper (mods.powerArmor.<slot>.<key>) → русское название
NAMES_RU = {
    "systeme.epurateurRadiations": "Радиационный скруббер",
    "systeme.detecteur": "Датчик",
    "systeme.athVisee": "Прицельный HUD",
    "systeme.baseDonnees": "Внутренняя база данных",
    "systeme.noyauReacteur": "Реакторный узел",
    "systeme.purificateurSanguin": "Очиститель крови",
    "systeme.protocolesUrgence": "Протоколы ЧС",
    "systeme.servomoteursAssiste": "Сервоприводы движения",
    "systeme.dynamoCinetique": "Кинетическое динамо",
    "systeme.pompeMedicale": "Медицинский насос",
    "systeme.plaquesReactives": "Реактивные пластины",
    "systeme.bobinesTesla": "Катушки Теслы",
    "systeme.stealthBoy": "Стелс-бой",
    "systeme.jetpack": "Реактивный ранец",
    "systeme.barreArmature": "Вваренная арматура",
    "systeme.poingRouille": "Ржавые кулаки",
    "systeme.braceletsHydrauliques": "Гидравлические наручи",
    "systeme.braceletsOptimises": "Оптимизированные наручи",
    "systeme.braceletsTesla": "Тесловы наручи",
    "systeme.amortisseursCalibres": "Калиброванные амортизаторы",
    "systeme.eventExplosion": "Взрывной клапан",
    "systeme.servomoteursVitesse": "Форсированные сервоприводы",
    "blindage.titane": "Титановая обшивка",
    "blindage.plomb": "Свинцовая обшивка",
    "blindage.photovoltaique": "Фотоэлектрическое покрытие",
    "blindage.antigel": "Антифризное покрытие",
    "blindage.prismatique": "Призматическая обшивка",
    "blindage.antiexplosion": "Противоосколочная обшивка",
    "blindage.protectionIem": "ЭМИ-защита",
    "amelioration.raider2": "Рейдер II",
    "amelioration.t45b": "Т-45b",
    "amelioration.t45c": "Т-45c",
    "amelioration.t45d": "Т-45d",
    "amelioration.t45e": "Т-45e",
    "amelioration.t45f": "Т-45f",
    "amelioration.t51b": "Т-51b",
    "amelioration.t51c": "Т-51c",
    "amelioration.t51d": "Т-51d",
    "amelioration.t51e": "Т-51e",
    "amelioration.t51f": "Т-51f",
    "amelioration.t60b": "Т-60b",
    "amelioration.t60c": "Т-60c",
    "amelioration.t60d": "Т-60d",
    "amelioration.t60e": "Т-60e",
    "amelioration.t60f": "Т-60f",
    "amelioration.mk2": "Mk II",
    "amelioration.mk3": "Mk III",
    "amelioration.mk4": "Mk IV",
    "amelioration.mk5": "Mk V",
    "amelioration.mk6": "Mk VI",
}

# Те же ключи, что выше; строки сверены с front/src/i18n/locales/en.ts.
NAMES_EN = {
    "systeme.epurateurRadiations": "Radiation Scrubber",
    "systeme.detecteur": "Sensor",
    "systeme.athVisee": "Targeting HUD",
    "systeme.baseDonnees": "Internal Database",
    "systeme.noyauReacteur": "Core Assembly",
    "systeme.purificateurSanguin": "Blood Cleanser",
    "systeme.protocolesUrgence": "Emergency Protocols",
    "systeme.servomoteursAssiste": "Motion-Assist",
    "systeme.dynamoCinetique": "Kinetic Dynamo",
    "systeme.pompeMedicale": "Medic Pump",
    "systeme.plaquesReactives": "Reactive Plates",
    "systeme.bobinesTesla": "Tesla Coils",
    "systeme.stealthBoy": "Stealth Boy",
    "systeme.jetpack": "Jetpack",
    "systeme.barreArmature": "Welded Rebar",
    "systeme.poingRouille": "Rusty Knuckles",
    "systeme.braceletsHydrauliques": "Hydraulic",
    "systeme.braceletsOptimises": "Optimized",
    "systeme.braceletsTesla": "Tesla",
    "systeme.amortisseursCalibres": "Calibrated Shocks",
    "systeme.eventExplosion": "Explosion Vent",
    "systeme.servomoteursVitesse": "Overdrive",
    "blindage.titane": "Titanium",
    "blindage.plomb": "Lead",
    "blindage.photovoltaique": "Photovoltaic",
    "blindage.antigel": "Winterized",
    "blindage.prismatique": "Prism",
    "blindage.antiexplosion": "Blast-Proof",
    "blindage.protectionIem": "EMP Shielding",
    "amelioration.raider2": "Raider II",
    "amelioration.t45b": "T-45b",
    "amelioration.t45c": "T-45c",
    "amelioration.t45d": "T-45d",
    "amelioration.t45e": "T-45e",
    "amelioration.t45f": "T-45f",
    "amelioration.t51b": "T-51b",
    "amelioration.t51c": "T-51c",
    "amelioration.t51d": "T-51d",
    "amelioration.t51e": "T-51e",
    "amelioration.t51f": "T-51f",
    "amelioration.t60b": "T-60b",
    "amelioration.t60c": "T-60c",
    "amelioration.t60d": "T-60d",
    "amelioration.t60e": "T-60e",
    "amelioration.t60f": "T-60f",
    "amelioration.mk2": "Mk II",
    "amelioration.mk3": "Mk III",
    "amelioration.mk4": "Mk IV",
    "amelioration.mk5": "Mk V",
    "amelioration.mk6": "Mk VI",
}

# тексты эффектов helper (en.ts → mods.effects.pa.*) по-русски
EFFECTS_RU = {
    "radiationPurifier": "Игнорируйте радиационный урон от облучённой еды и "
                         "напитков, потреблённых, пока броня под питанием.",
    "sensor": "Пока броня под питанием, вы можете перебрасывать 1d20 "
              "во всех проверках ВОС.",
    "targetingHud": "Малое действие «Прицеливание» позволяет совершить второе "
                    "малое действие за 0 ОД, пока броня под питанием.",
    "internalDatabase": "Пока броня под питанием, вы можете перебрасывать 1d20 "
                        "во всех проверках ИНТ.",
    "weldenRebar": "Противник, атаковавший вас в ближнем бою и получивший "
                   "осложнение, получает 2 БК урона.",
    "reactorCore": "Пока броня под питанием: если в начале вашего хода пул ОД "
                   "группы пуст, добавьте в него +1 ОД.",
    "bloodCleanser": "Пока броня под питанием, вы можете перебросить бросок "
                     "привыкания от вызывающих зависимость препаратов.",
    "emergencyProtocols": "Пока броня под питанием и ваш ОЗ ниже четверти "
                          "максимума, получите +1 к Защите и +3 ко всем "
                          "сопротивлениям урону.",
    "motionAssistServos": "Пока броня под питанием, СИЛ каркаса становится 13.",
    "kineticDynamo": "Пока броня под питанием, получив урон (после снижения "
                     "СУ), добавьте +1 ОД в пул группы.",
    "medicalPump": "Пока броня под питанием, когда ваш ОЗ падает ниже "
                   "половины, вы сразу используете стимулятор: 3 ОЗ "
                   "или 1 рана.",
    "reactivePlates": "Пока броня под питанием, получив урон от ближней атаки, "
                      "вы наносите нападающему половину выпавшего урона "
                      "(физический).",
    "teslaCoils": "Пока броня под питанием, каждый противник, атаковавший вас "
                  "в ближнем бою, получает 4 БК энергетического урона.",
    "stealthBoy": "Вы можете активировать стелс-бой раз за сцену, "
                  "потратив 1 заряд.",
    "jetpack": "Перемещаясь, вы можете потратить 1 заряд ранца и пройти "
               "на 1 зону больше (по горизонтали или вертикали).",
    "hydraulicBracers": "Пока броня под питанием, ваши безоружные атаки "
                        "наносят +2 БК урона.",
    "optimizedBracers": "Пока броня под питанием, вы можете потратить до 4 ОД "
                        "как бонусный урон в ближнем бою.",
    "teslaBracers": "Пока броня под питанием, безоружные атаки наносят "
                    "+2 БК урона, и этот урон энергетический.",
    "explosionVent": "Пока броня под питанием, приземляясь с высоты, вы "
                     "наносите 4 БК урона всем существам и объектам "
                     "на близкой дистанции.",
    "overdriveServos": "Пока броня под питанием, при беге вы можете потратить "
                       "+2 ОД и пройти на 1 зону больше.",
    "photovoltaic": "+1 ОД в начале сцены, если вы под прямым солнечным "
                    "светом (срабатывает один раз).",
    # общие эффекты брони (mods.effects.*, не pa.*)
    "blastResist2": "+2 ко всем сопротивлениям урону от взрывного оружия.",
}

# Английские тексты из mods.effects.pa.* и mods.effects.* в en.ts.
EFFECTS_EN = {
    "radiationPurifier": "Ignore radiation damage from Irradiated food or drink consumed while the armor is powered",
    "sensor": "You may reroll 1d20 on all PER tests while the armor is powered",
    "targetingHud": "When you take the Aim minor action, you may take a second minor action for 0 AP while the armor is powered",
    "internalDatabase": "You may reroll 1d20 on all INT tests while the armor is powered",
    "weldenRebar": "Enemies who make a melee or unarmed attack against you and suffer a complication take 2 CD damage",
    "reactorCore": "While the armor is powered, if the group AP pool is empty at the start of your turn, add +1 AP to it",
    "bloodCleanser": "You may reroll the addiction roll for addictive chems while the armor is powered",
    "emergencyProtocols": "While the armor is powered, if your current HP is below a quarter of your maximum, add +1 to your Defense and +3 to all your damage resistances",
    "motionAssistServos": "The frame's STR becomes 13 while the armor is powered",
    "kineticDynamo": "While the armor is powered, when you take damage (after DR reduction), add +1 AP to the group pool",
    "medicalPump": "While the armor is powered, when your HP drops below half of your maximum, you immediately use a Stimpak and recover 3 HP or treat 1 wound",
    "reactivePlates": "While the armor is powered, when you take damage from a melee or unarmed attack, you deal half the damage roll total back to the attacker (ballistic)",
    "teslaCoils": "While the armor is powered, each time an enemy makes a melee attack against you, they take 4 CD energy damage",
    "stealthBoy": "You may activate a Stealth Boy once per scene by spending 1 charge",
    "jetpack": "When you move, you may activate a jetpack by spending 1 charge, allowing you to move 1 extra zone (horizontal or vertical)",
    "hydraulicBracers": "While the armor is powered, your unarmed attacks deal +2 CD damage",
    "optimizedBracers": "While the armor is powered, you may spend up to 4 AP as bonus damage for melee attacks",
    "teslaBracers": "While the armor is powered, your unarmed attacks deal +2 CD damage. The damage from these attacks is energy.",
    "explosionVent": "While the armor is powered, when you land from a height, you deal 4 CD damage to all creatures and objects at close range",
    "overdriveServos": "While the armor is powered, when you sprint, you may spend +2 AP to move 1 extra zone",
    "photovoltaic": "+1 AP at the start of a scene if you are in direct sunlight (applies only once)",
    "blastResist2": "+2 to all damage resistances against Blast weapons",
}

STAT_FIELDS = {
    "ballisticResistance": "physicalDamageRating",
    "energyResistance": "energyDamageRating",
    "radiationResistance": "radiationDamageRating",
    "hpBonus": "hp",
}
PERK_RU = {"armorer": "Бронник", "science": "Наука", "blacksmith": "Кузнец"}
PERK_EN = {"armorer": "Armorer", "science": "Science", "blacksmith": "Blacksmith"}
QUALITY_RU = {"persistent": "Постоянный"}
QUALITY_EN = {"persistent": "Persistent"}


def rus_name(key: str) -> str:
    """Русское название мода по его helper-ключу."""
    parts = key.split(".")
    base = NAMES_RU.get(".".join(parts[:2]), key)
    if parts[0] == "amelioration":
        return f"{base} · {PARTS_RU.get(parts[-1], parts[-1])}"
    return base


def english_name(key: str) -> str:
    """English name from the same helper key used for the Russian i18n."""
    parts = key.split(".")
    base = NAMES_EN.get(".".join(parts[:2]), key)
    if parts[0] == "amelioration":
        return f"{base} {PARTS_EN.get(parts[-1], parts[-1])}"
    return base


def entries_from_ts(text: str) -> list[dict]:
    """Записи модов силовой брони из mods.ts."""
    out: list[dict] = []
    for match in re.finditer(r"^  \{\n(.*?)^  \},", text, re.S | re.M):
        body = match.group(1)
        if "applicableTo: 'powerArmor'" not in body:
            continue
        key = re.search(r"nameAddKey: 'mods\.powerArmor\.([^']+)\.nameAdd'", body)
        slot = re.search(r"slot: '(\w+)'", body)
        name = re.search(r"name: '((?:[^'\\]|\\.)*)'", body)
        weight = re.search(r"weightChange: ([\d.]+)", body)
        cost = re.search(r"cost: ([\d.]+)", body)
        if not (key and slot and weight and cost):
            continue
        entry = {
            "key": key.group(1),
            "helperName": name.group(1).replace("\\'", "'") if name else "",
            "slot": slot.group(1),
            "weight": float(weight.group(1)),
            "cost": int(float(cost.group(1))),
            "perks": [],
            "effects": [],
        }
        for perk in re.finditer(
                r"requiredPerk(?:\d)?: '(\w+)', requiredPerkRank(?:\d)?: (\d+)",
                body):
            entry["perks"].append(
                f"{PERK_RU.get(perk.group(1), perk.group(1))} {perk.group(2)}")
        for effect in re.finditer(r"\{ effectType: '(\w+)'(.*?)\}", body):
            kind, rest = effect.group(1), effect.group(2)
            item: dict = {"type": kind}
            value = re.search(r"numericValue: ([\d.]+)", rest)
            if value:
                number = float(value.group(1))
                item["value"] = int(number) if number.is_integer() else number
            quality = re.search(r"qualityName: '(\w+)'", rest)
            if quality:
                item["quality"] = quality.group(1)
            desc = re.search(r"descriptionKey: '([^']+)'", rest)
            if desc:
                item["description"] = desc.group(1).split(".")[-1]
            entry["effects"].append(item)
        out.append(entry)
    return out


def mod_id(key: str) -> str:
    return "pa_" + re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


def to_equipment(entries: list[dict]) -> list[dict]:
    """Записи модов в формате armor_mods.json компаньона (+ helper-поля)."""
    mods: list[dict] = []
    for entry in entries:
        keys = entry["key"].split(".")
        areas = ["Body", "Hand", "Leg"]
        if entry["slot"] == "amelioration" and len(keys) > 2:
            areas = PART_AREAS.get(keys[-1], areas)
        identifier = mod_id(entry["key"])
        mod = {
            "id": identifier,
            "modType": "powerArmor",
            "modSlot": entry["slot"],
            "modSlotRu": SLOT_RU[entry["slot"]],
            "protectedAreas": areas,
            "weightModifier": {"op": "+", "value": entry["weight"]},
            "costModifier": {"op": "+", "value": entry["cost"]},
            "requiredPerk": " / ".join(entry["perks"]),
            "statModifiers": {},
            "specialEffects": [],
            "helperKey": entry["key"],
            "helperName": entry["helperName"],
        }
        if entry["slot"] == "amelioration":
            mod["upgradeGroup"] = keys[1]
        for effect in entry["effects"]:
            kind = effect["type"]
            if kind in STAT_FIELDS:
                mod["statModifiers"][STAT_FIELDS[kind]] = {
                    "op": "+", "value": effect.get("value", 0)}
            elif kind == "carryCapacity":
                mod["specialEffects"].append({
                    "id": f"effect_pa_{identifier}_carry",
                    "description": f"+{effect.get('value', 0)} к максимальному "
                                   f"весу."})
            elif kind == "gainQuality":
                quality = QUALITY_RU.get(effect.get("quality", ""),
                                         effect.get("quality", ""))
                mod["specialEffects"].append({
                    "id": f"effect_pa_{identifier}_quality",
                    "description": f"Атаки получают качество «{quality}»."})
            elif kind == "special":
                key = effect.get("description", "")
                text = EFFECTS_RU.get(key)
                if text:
                    mod["specialEffects"].append(
                        {"id": f"effect_pa_{key}", "description": text})
        mods.append(mod)
    return mods


def english_special_effects(entry: dict, identifier: str) -> list[dict]:
    """English descriptions for non-numeric helper effects."""
    effects: list[dict] = []
    for effect in entry["effects"]:
        kind = effect["type"]
        if kind == "carryCapacity":
            effects.append({
                "id": f"effect_pa_{identifier}_carry",
                "description": f"+{effect.get('value', 0)} to maximum carry weight.",
            })
        elif kind == "gainQuality":
            quality = QUALITY_EN.get(effect.get("quality", ""),
                                     effect.get("quality", ""))
            effects.append({
                "id": f"effect_pa_{identifier}_quality",
                "description": f"Attacks gain the {quality} quality.",
            })
        elif kind == "special":
            key = effect.get("description", "")
            text = EFFECTS_EN.get(key)
            if text:
                effects.append({"id": f"effect_pa_{key}", "description": text})
    return effects


def english_i18n(entries: list[dict]) -> list[dict]:
    """English i18n records matching the generated power-armor mod IDs."""
    return [
        {
            "id": mod_id(entry["key"]),
            "name": english_name(entry["key"]),
            "specialEffects": english_special_effects(entry, mod_id(entry["key"])),
        }
        for entry in entries
    ]


# -- совместимость ----------------------------------------------------------


def _const_list(text: str, name: str) -> list[str]:
    """Содержимое `const X = [ … ]` как список строк."""
    match = re.search(rf"const {name} = \[(.*?)\];", text, re.S)
    if not match:
        return []
    return [m.replace("\\'", "'")
            for m in re.findall(r"'((?:[^'\\]|\\.)*)'", match.group(1))]


def compat_from_ts(text: str) -> dict[str, list[str]]:
    """POWER_ARMOR_COMPATIBILITY, раскрытая по деталям.

    Списки в helper собираются из констант (`...PA_SYSTEM_HEAD`,
    `...PA_PLATING`) и фильтра `PA_PLATING_X01`, поэтому их надо раскрыть.
    """
    consts: dict[str, list[str]] = {}
    for name in re.findall(r"^const (PA_[A-Z0-9_]+|BALLISTIC_WEAVE|"
                           r"VAULT_SUIT_MODS) = \[", text, re.M):
        consts[name] = _const_list(text, name)
    if "PA_PLATING" in consts:
        consts["PA_PLATING_X01"] = [m for m in consts["PA_PLATING"]
                                    if m != "Revêtement antigel"]

    start = text.index("export const POWER_ARMOR_COMPATIBILITY")
    end = text.index("];", start)
    groups: dict[str, list[str]] = {}
    pattern = re.compile(
        r"\{ itemName: '((?:[^'\\]|\\.)*)', modNames: \[(.*?)\] \}", re.S)
    for match in pattern.finditer(text[start:end]):
        name = match.group(1).replace("\\'", "'")
        body = match.group(2)
        items = [m.replace("\\'", "'") for m in
                 re.findall(r"'((?:[^'\\]|\\.)*)'", body)]
        expanded: list[str] = []
        for item in items:
            expanded.extend(consts.get(item, [item]))
        for const in re.findall(r"\.\.\.(PA_[A-Z0-9_]+)", body):
            expanded.extend(consts.get(const, []))
        groups[name] = expanded
    return groups


# -- запись -----------------------------------------------------------------


def write(entries: list[dict], equipment: Path) -> list[dict]:
    mods = to_equipment(entries)
    slug = []
    for mod in mods:
        item = {
            "id": mod["id"],
            "modType": mod["modType"],
            "modSlot": mod["modSlot"],
            "modSlotRu": mod["modSlotRu"],
            "protectedAreas": mod["protectedAreas"],
            "weightModifier": mod["weightModifier"],
            "costModifier": mod["costModifier"],
            "requiredPerk": mod["requiredPerk"],
            "statModifiers": mod["statModifiers"],
            "helperKey": mod["helperKey"],
            "helperName": mod["helperName"],
        }
        if "upgradeGroup" in mod:
            item["upgradeGroup"] = mod["upgradeGroup"]
        slug.append(item)
    equipment.mkdir(parents=True, exist_ok=True)
    (equipment / "powerArmor_mods.json").write_text(
        json.dumps(slug, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    ru = [{"id": mod["id"], "name": rus_name(mod["helperKey"]),
           "specialEffects": mod["specialEffects"]} for mod in mods]
    i18n_root = equipment.parent / "i18n"
    ru_dir = i18n_root / "ru-RU" / "data" / "equipment" / "armor"
    ru_dir.mkdir(parents=True, exist_ok=True)
    (ru_dir / "powerArmor_mods.json").write_text(
        json.dumps(ru, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    en_dir = i18n_root / "en-EN" / "data" / "equipment" / "armor"
    en_dir.mkdir(parents=True, exist_ok=True)
    (en_dir / "powerArmor_mods.json").write_text(
        json.dumps(english_i18n(entries), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    return mods


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("helper", help="путь к клону Fallout-2d20-helper")
    ap.add_argument("--out", default=str(ROOT / "data" / "companion" / "equipment"))
    args = ap.parse_args(argv)

    helper = Path(args.helper)
    mods_ts = (helper / "back/src/db/seed/data/mods.ts").read_text(encoding="utf-8")
    compat_ts = (helper / "back/src/db/seed/data/itemModCompatibility.ts"
                 ).read_text(encoding="utf-8")

    entries = entries_from_ts(mods_ts)
    if not entries:
        raise SystemExit("в mods.ts не найдено модов силовой брони")
    equipment = Path(args.out)
    mods = write(entries, equipment)

    compat = compat_from_ts(compat_ts)
    (equipment / "powerArmor_modCompatibility.json").write_text(
        json.dumps(compat, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    counts = {slot: sum(m["modSlot"] == slot for m in mods)
              for slot in SLOT_RU}
    print(f"модов: {len(mods)} " + ", ".join(
        f"{name}: {counts[slot]}" for slot, name in SLOT_RU.items()))
    print(f"совместимость: {len(compat)} деталей, "
          f"модов на деталь: {min(len(v) for v in compat.values())}…"
          f"{max(len(v) for v in compat.values())}")
    missing = [m["helperKey"] for m in mods
               if any(e.get("type") == "special" for e in
                      next(x for x in entries if x["key"] == m["helperKey"]
                           )["effects"]) and not m["specialEffects"]]
    if missing:
        print("без русского текста эффекта: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
