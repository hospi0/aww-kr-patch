# -*- coding: utf-8 -*-
"""유닛·지명 라틴 로마자 맵 (실명, 8칸 축약). ⚠️초안 — 사용자 검토 대상.

가나를 라틴으로 돌려 슬롯을 해방한다(한글 아님). 8칸 고정폭 표(유닛·GMDT지명)라 축약.
게임고유·불확실은 REVIEW 로 표시. 커버 못한 항목은 fill 시 미치환으로 남아 검출된다.
"""

# 서술형 유닛 → 라틴 군용 약어/영문 (한글유지분은 vocab_draft.DESC_HANGUL)
DESC_ROMAJI = {
    'センカン': 'BB', 'クチクカン': 'DD', 'センスイカン': 'SS',
    'ケイジュン': 'CL', 'ジュウジュン': 'CA', 'ケイクウボ': 'CVL',
    'ヨウサイ': 'Fort', 'マジノヨウサイ': 'Maginot',
    'テキダンヘイ': 'Grenadr', 'テキダンヘイ43': 'Grend43',
    'ギユウヘイ': 'Militia', 'ヨビエキヘイ': 'Reserve', 'ドウインヘイ': 'Levy',
    'クウテイタイ': 'Airborn', 'ホキュウシャ': 'Supply',
    'キカイカホヘイ': 'MechInf', 'ジドウシャホヘイ': 'MotInf', 'スキーホヘイ': 'SkiInf',
    'コウカリョウヘイ': 'Paratrp', 'セントウコウヘイ': 'CmbtEng',
    'コウチクジンチ': 'Fortif', 'コウシャホウトウ': 'AAturr', 'エンガンホウダイ': 'CoastGn',
    'ソウコウテキダン': 'PzGren', 'ソウコウヘイ': 'ArmInf',
    'SSソウコウヘイ': 'SSPzGr', 'エリートヘイ': 'Elite', 'エリートホヘイ': 'EliteI',
    'シンエイセキグン': 'GdRedA', 'レーダーキチ': 'Radar',
    'シュウヘイ': 'Marine', 'ホヘイ44': 'Inf44', 'Hガタセンカン': 'H-BB',
    'レイセン21ガタ': 'A6M2', 'ハヤブサⅠガタ': 'Ki43-I',
    # 세션5 확정: 서술형 유닛 전부 로마자 (예산상 한글 불가)
    'ホヘイ': 'Inf', 'コウヘイ': 'Eng', 'ソゲキヘイ': 'Sniper',
    'ユソウキ': 'TrspAir', 'ユソウシャ': 'Truck', 'ユソウセン': 'TrspShp',
}

# 유닛 베이스 토큰(가나) → 라틴. 뒤 모델기호(Ⅰ/Ⅱ/A/D/L/숫자)는 유지.
UNIT_BASE = {
    'パンター': 'Panther', 'ティーガー': 'Tiger', 'ヤクトティーガー': 'JgdTiger',
    'ヤクトパンター': 'JgdPanth', 'マチルダ': 'Matilda', 'クロムウェル': 'Cromwell',
    'チャーチル': 'Churchll', 'シャーマン': 'Sherman', 'グラント': 'Grant',
    'スチュアート': 'Stuart', 'クルセーダー': 'Crusader', 'チャレンジャー': 'Challngr',
    'チャーフィー': 'Chaffee', 'コメット': 'Comet', 'クロムウェル': 'Cromwell',
    'カヴェナンター': 'Covenatr', 'バレンタイン': 'Valentin', 'テトラーク': 'Tetrarch',
    'ローカスト': 'Locust', 'グレイハウンド': 'Greyhnd', 'スタッグハウンド': 'Staghnd',
    'ヘッツアー': 'Hetzer', 'ナースホルン': 'Nashorn', 'フンメル': 'Hummel',
    'エレファント': 'Elefant', 'マウス': 'Maus', 'ブルムベアー': 'Brummbar',
    'メーベルワーゲン': 'Mobelwgn', 'クーゲルブリッツ': 'Kugelbtz', 'オストウィンド': 'Ostwind',
    'ヴィルベルビンド': 'Wirblwnd', 'ヴェスペ': 'Wespe', 'グリーレ': 'Grille',
    'マーダー': 'Marder', 'ナッター': 'Natter', 'トルディ': 'Toldi', 'トウラン': 'Turan',
    'ゼモベンテ': 'Semovnt', 'セモベンテ': 'Semovnt', 'カルロ': 'Carro',
    'ソミュア': 'Somua', 'ルノー': 'Renault', 'ホチキス': 'Hotchkis', 'ダイムラー': 'Daimler',
    'ハンバー': 'Humber', 'カメ': 'Turtle', 'トリ': 'Bird', 'ドグウ': 'Dogu',
    'ゴリアテ': 'Goliath', 'カチューシャ': 'Katyusha', 'トータス': 'Tortoise',
    'シャルンホルスト': 'Scharnhr', 'グナイゼナウ': 'Gneisenu', 'ビスマルク': 'Bismarck',
    'テルピッツ': 'Tirpitz', 'アドミラル': 'Admiral', 'リュッツオウ': 'Lutzow',
    'シェアー': 'Scheer', 'ヒッパー': 'Hipper', 'ケーニヒ': 'Konig',
    # 항공기
    'スピット': 'Spitfir', 'スピットファイア': 'Spitfir', 'シーファイア': 'Seafire',
    'ハリケーン': 'Hurricn', 'テンペスト': 'Tempest', 'タイフーン': 'Typhoon',
    'モスキート': 'Mosquito', 'ランカスター': 'Lancastr', 'ハリファクス': 'Halifax',
    'ウェリントン': 'Welingtn', 'ブレニム': 'Blenheim', 'ボーフォート': 'Beaufort',
    'ビューフォート': 'Beaufort', 'ソードフィッシュ': 'Swordfsh', 'フルマー': 'Fulmar',
    'マスタング': 'Mustang', 'サンダーボルト': 'Thundblt', 'ライトニング': 'Lightnng',
    'エアラコブラ': 'Airacbra', 'ウォーホーク': 'Warhawk', 'ウオーホーク': 'Warhawk',
    'キティホーク': 'Kittyhwk', 'ヘルキャット': 'Hellcat', 'ワイルドキャット': 'Wildcat',
    'ベアキャット': 'Bearcat', 'コルセア': 'Corsair', 'アベンジャー': 'Avenger',
    'ドーントレス': 'Dauntlss', 'ヘルダイバー': 'Helldivr', 'デバステーター': 'Devastat',
    'カタリナ': 'Catalina', 'マローダー': 'Marauder', 'ミッチェル': 'Mitchell',
    'ハボック': 'Havoc', 'インベーダー': 'Invader', 'ブラックウィドウ': 'BlkWidow',
    'コメット': 'Comet', 'メテオ': 'Meteor', 'ミーティア': 'Meteor', 'バンパイア': 'Vampire',
    'フォッカー': 'Fokker', 'ブレゲ': 'Breguet', 'ポテ': 'Potez', 'ブロック': 'Bloch',
    'デファイント': 'Defiant', 'グラジュエーター': 'Gladiatr', 'スキュア': 'Skua',
    'バラクーダ': 'Barracda', 'ファイアフライ': 'Firefly', 'ワールウインド': 'Whirlwnd',
    'ホーク': 'Hawk', 'イーグル': 'Eagle', 'ナイトホーク': 'Nighthwk', 'ホーネット': 'Hornet',
    'テキサス': 'Texas', 'アイオワ': 'Iowa', 'エセックス': 'Essex', 'サラトガ': 'Saratoga',
    'レキシントン': 'Lexingtn', 'ヨークタウン': 'Yorktown', 'エンタープライズ': 'Entrpris',
    'レンジャー': 'Ranger', 'ワスプ': 'Wasp', 'ホーネット': 'Hornet',
    'ノースカロライナ': 'N.Carol', 'ワシントン': 'Washngtn', 'ネルソン': 'Nelson',
    'フッド': 'Hood', 'リシュリュー': 'Richelieu'.replace('u', '')[:8], 'リットリオ': 'Littorio',
    'リベレーター': 'Liberatr', 'フライングラム': 'Flyngram',
}

# 지명(가나) → 라틴 실명 (8칸 축약). ⚠️게임고유·불확실은 아래 REVIEW.
PLACES = {
    'アーヘン': 'Aachen', 'ブリュッセル': 'Brussels', 'セダン': 'Sedan', 'ディナン': 'Dinant',
    'ル·アーブル': 'LeHavre', 'カレー': 'Calais', 'ドーバー': 'Dover', 'ポーツマス': 'Portsmth',
    'ビル·ハケイム': 'BirHakem', 'トブルク': 'Tobruk', 'ニス': 'Nice', 'ベオグラード': 'Belgrade',
    'サラエボ': 'Sarajvo', 'ルヴォフ': 'Lvov', 'クレムリン': 'Kremlin', 'ワルシャワ': 'Warsaw',
    'クトノ': 'Kutno', 'ミンスク': 'Minsk', 'スモレンスク': 'Smolensk', 'ゴメル': 'Gomel',
    'モスクワ': 'Moscow', 'キエフ': 'Kiev', 'ロンドン': 'London', 'パリ': 'Paris',
    'ローマ': 'Rome', 'ナポリ': 'Naples', 'ダンケルク': 'Dunkirk', 'アントワープ': 'Antwerp',
    'アミアン': 'Amiens', 'カーン': 'Caen', 'シェルブール': 'Cherbrg', 'ブレスト': 'Brest',
    'ナント': 'Nantes', 'レンヌ': 'Rennes', 'ル·マン': 'LeMans', 'ロッテルダム': 'Rotterdm',
    'ブダペスト': 'Budapest', 'ハリコフ': 'Kharkov', 'クルスク': 'Kursk', 'オリョール': 'Orel',
    'ロストフ': 'Rostov', 'ケーニヒスベルグ': 'Konigsbg', 'ダンツィヒ': 'Danzig',
    'ポズナニ': 'Poznan', 'クラカウ': 'Krakow', 'ロッズ': 'Lodz', 'ラドム': 'Radom',
    'ヴレスラウ': 'Breslau', 'S·グラード': 'Stalngrd', 'Sグラード': 'Stalngrd',
    'ビアリストク': 'Bialystk', 'トゥーラ': 'Tula', 'ツーラ': 'Tula', 'バクー': 'Baku',
    'カラチ': 'Karachi', 'カーン': 'Caen', 'メッシナ': 'Messina', 'パレルモ': 'Palermo',
    'カタニア': 'Catania', 'シラクザ': 'Syracus', 'ジェラ': 'Gela', 'リカタ': 'Licata',
    'レッジョ': 'ReggioC', 'ペスカラ': 'Pescara', 'アンツィオ': 'Anzio', 'テルモリ': 'Termoli',
    'ベンガジ': 'Benghazi'[:8], 'デルナ': 'Derna', 'トリポリ': 'Tripoli', 'テベサ': 'Tebessa',
    'アレキサンドリア': 'Alexndra', 'カイロ': 'Cairo', 'エルアラメイン': 'ElAlamn',
    'エル·ダバ': 'ElDaba', 'エル·アデム': 'ElAdem', 'アブキール': 'Aboukir',
    'シチリア': 'Sicily', 'マルタ': 'Malta', 'アクイラ': 'Aquila',
    'ニューヨーク': 'NewYork', 'ボストン': 'Boston', 'デトロイト': 'Detroit',
    'ワシントン': 'Washngtn', 'トロント': 'Toronto', 'モントリオール': 'Montreal',
    'シドニー': 'Sydney', 'バーミンガム': 'Birmnghm', 'ブリストル': 'Bristol',
    'リバプール': 'Livrpool', 'プリマス': 'Plymouth', 'ブライトン': 'Brighton',
    'ハリファクス': 'Halifax', 'バハマチ': 'Bahamas', 'マハガナ': 'Mahagana',
    'フランクフルト': 'Frankfrt', 'シュテッティン': 'Stettin', 'ゲルリツ': 'Gorlitz',
    'オストラヴァ': 'Ostrava', 'コマーロム': 'Komarom', 'ヴェスプレーム': 'Veszprem',
    'アンジェ': 'Angers', 'シャルトル': 'Chartres'[:8], 'ブローニュ': 'Boulogne'[:8],
    'サン·ナゼール': 'StNazair', 'サン·ロー': 'StLo', 'サン·ヴィット': 'StVith',
    'サン·ローラン': 'StLauren', 'バイユー': 'Bayeux', 'アロマンシェ': 'Arromnch',
    'ウィストルアム': 'Ouistrhm', 'ナイメーヘン': 'Nijmegen'[:8], 'マーストリヒト': 'Maastrht',
    'リエージュ': 'Liege', 'ナミュール': 'Namur', 'ヴェルヴィエ': 'Verviers'[:8],
    'バストーニュ': 'Bastogne'[:8], 'モンコルネ': 'Montcorn', 'アルジャンタン': 'Argentan',
    'ブルゼミスル': 'Przemysl', 'キエルツェ': 'Kielce', 'ウッジ': 'Lodz',
    'ミハイロフカ': 'Mikhaylv', 'メリトポリ': 'Melitopl', 'ザポロジェ': 'Zaporozh',
    'ドネツク': 'Donetsk', 'スタリノ': 'Stalino', 'ヴォロネジ': 'Voronezh'[:8],
    'オリョール': 'Orel', 'ベルゴロド': 'Belgorod'[:8], 'スーミ': 'Sumy',
    'チェルカッスイ': 'Cherkasy', 'カネフ': 'Kanev', 'クレメンチェク': 'Kremnchk',
    'ノヴォモスコフス': 'NovoMskv', 'カリーニン': 'Kalinin', 'ヴィヤジマ': 'Vyazma',
    'モジャイスク': 'Mozhaysk'[:8], 'トビリシ': 'Tbilisi', 'エレバン': 'Yerevan',
    'アストラハン': 'Astrakhn', 'エリスタ': 'Elista', 'グムラク': 'Gumrak',
    'イジューム': 'Izyum', 'コテルニコブ': 'Kotelnik', 'ザポロジェ': 'Zaporzh',
    'ロブノ': 'Rovno', 'ロスラウリ': 'Roslavl', 'ゴメル': 'Gomel', 'ネシン': 'Nezhin',
    # 일본
    'イヌヤマ': 'Inuyama', 'キヨス': 'Kiyosu', 'オーガキ': 'Ogaki', 'タケガハナ': 'Takeghn',
    # 게임고유
    'コダイイセキ': 'Ruins', 'コッカイギジドウ': 'Parlmnt', 'ソウトウカンテイ': 'Chancll',
    'エキ': 'Stn', 'クウコウ': 'Airport', 'コウジョウ': 'Factory', 'トシ': 'City',
    'ミナト': 'Port', 'ハシ': 'Bridge',
}

# 2차 보강 — 미커버 유닛 (실명, 8칸축약)
UNIT_BASE.update({
    'ヤホウ': 'FG', 'AAホウ': 'AA', 'トム': 'Tom', 'ロングトム': 'LTom',
    'ウチュウジン': 'Alien', 'ボフォース': 'Bofors', 'ドリア': 'Doria', 'バトル': 'Battle',
    'ツエッペリン': 'Zeppeln', 'ロドリゲス': 'Rodrigz', 'ジャクソン': 'Jacksn',
    'カリオペ': 'Caliope', 'プリースト': 'Priest', 'ソベリン': 'Sovern', 'ソユーズ': 'Soyuz',
    'アキリーズ': 'Achilles', 'アクイラ': 'Aquila', 'アークロイヤル': 'ArkRoyal',
    'イーズィーエイト': 'EasyEght', 'ウルバリン': 'Wolverin', 'エアラコメット': 'Airacmt',
    'エバンエマール': 'EbenEml', 'カール': 'Karl', 'キングジョージ': 'KGeorge',
    'ケーリアン': 'Kerian', 'ジャンボ': 'Jumbo', 'ジークフリート': 'Siegfrd',
    'スカイレーダー': 'Skyradr', 'ズリーニィ': 'Zrinyi', 'セクストン': 'Sexton',
    'デマーグ': 'Demag', 'トーチカ': 'Pillbox', 'ニムロード': 'Nimrod', 'ハーミス': 'Hermes',
    'バッファロー': 'Buffalo', 'パーシング': 'Pershng', 'ビショップ': 'Bishop',
    'ファーマ': 'Farman', 'フューリアス': 'Furious', 'ブレダ': 'Breda', 'ベアルン': 'Bearn',
    'マウルティア': 'Maultir', 'マーチン': 'Martin', 'マートレット': 'Martlet', 'リー': 'Lee',
    'レッドデビルズ': 'RedDevls', 'レバルス': 'Repulse', 'ロングトム': 'LTom',
    'ガタ': '', 'キュウ': '', 'ポンド': 'Pdr', 'ホウ': 'G',    # 型/級 접미 = 드롭 (Iowaガタ→Iowa)
})

# 2차 보강 — 미커버 지명 (실명 or 음차, 8칸축약)
PLACES.update({
    'リトフスク': 'Litovsk', 'ウィルナ': 'Vilna', 'カッセリーヌ': 'Kasserin', 'カブサ': 'Gafsa',
    'ガブリロフカ': 'Gavrilvk', 'ギーフ': 'Gifu', 'クラグエヴァツ': 'Kraguvac',
    'コンスタンチーヌ': 'Constntn', 'シディ·レゼク': 'SidiRzeg', 'シディアゼイス': 'SidiAzz',
    'シディスレイマン': 'SidiSlmn', 'シモントルニヤ': 'Simontr', 'スタンモア': 'Stanmore',
    'セフスク': 'Sevsk', 'ソベッキー': 'Sovetsky', 'チェンストノヴァ': 'Czstchwa',
    'ドナペンデレ': 'Dunapnt', 'ドブロニク': 'Dubrovnk', 'パルディア': 'Bardia',
    'ファストフ': 'Fastov', 'メギリ': 'Megiri', 'ル·ケフ': 'LeKef', 'ルケフ': 'LeKef',
    'ロムヌイ': 'Romny', 'ヴォロシロフグラ': 'Voroshlv', 'イワンティエフカ': 'Ivantevk',
    'クレメンチェク': 'Kremnchk', 'ポルタノヴァ': 'Poltava',
})

# 미검증/게임고유 접두·접미 (REVIEW 필요, 초안값)
REVIEW = {
    'グンキョテン': 'Base', 'グンシレイブ': 'HQ', 'トセンジョウ': 'Ferry', 'ベース': 'Base',
    'エキ': 'Stn', 'ハリコフ': 'Kharkov',
}
