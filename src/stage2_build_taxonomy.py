# -*- coding: utf-8 -*-
"""Build business_taxonomy_v1.json + archetypes.jsonl (Stage 1C + Stage 2A).

Archetypes focus on role relations, event patterns, dialogue evidence and benign
confusions — never operational crime details (plan §29).
Tuple: (subtype, roles, latent_facts, observable_signals, benign_confusions, risks)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "crime_chat_dataset"

TAXONOMY = {
    "fraud_scam": {
        "name": "诈骗",
        "subtypes": ["trust_building_progression", "investment_lead", "impersonation",
                     "refund_deposit_bait", "part_time_task", "loan_fee_bait",
                     "romance_pig_butchering", "account_lending", "escort_payment_claim",
                     "prize_fee", "customer_service_reverse", "second_hand_deposit_run"],
    },
    "bribery_corruption": {
        "name": "贿赂/利益输送",
        "subtypes": ["intermediary_payment_after_result", "consulting_fee_disguise",
                     "gift_card_channel", "relative_employment_exchange",
                     "project_bid_kickback", "regulatory_tip_payment",
                     "procurement_price_padding", "promotion_payment",
                     "school_admission_payment", "medical_channel_fee",
                     "invoice_rebate", "contract_signature_fee"],
    },
    "contraband_illicit_trade": {
        "name": "违禁品交易",
        "subtypes": ["batch_quantity_pickup", "code_word_catalog", "cross_region_shipping",
                     "prescription_diversion", "replica_counterfeit", "wildlife_trade",
                     "tool_weapon_parts", "e_cigarette_illegal_flavor",
                     "exam_leak_material", "sim_card_pool", "fuel_tax_evasion", "tobacco_smuggle"],
    },
    "violence_extortion": {
        "name": "暴力/寻衅",
        "subtypes": ["debt_collection_threat", "protection_fee", "gang_intimidation",
                     "hired_standing_off", "revenge_stalking_plan", "beat_example_warning",
                     "territory_warning", "online mob_doxx_attack", "kidnapping_threat_act",
                     "asset_seizure_force", "witness_intimidation", "settlement_by_force"],
    },
    "sexual_transaction_exploitation": {
        "name": "性交易/剥削",
        "subtypes": ["escort_arrangement", "introductory_middleman", "platform_referral",
                     "photo_material_trade", "minor_grooming_signal", "cam_room_fee_split",
                     "hotel_on_site_coordination", "long_term_support_exchange",
                     "model_recruitment_bait", "overseas_tour_group", "debt_body_exchange", "live_stream_reward_launder"],
    },
    "privacy_doxxing": {
        "name": "隐私侵害/人肉",
        "subtypes": ["id_address_lookup", "phone_number_trace", "travel_record_query",
                     "family_info_dump", "social_thread_expose", "workplace_contact_out",
                     "medical_record_browse", "purchase_data_resell",
                     "location_share_tracking", "chat_log_export", "face_search", "courier_info_leak"],
    },
    "money_laundering_obfuscation": {
        "name": "洗钱/资金掩饰",
        "subtypes": ["card_four_piece_pool", "split_transfer_chain", "crypto_offramp",
                     "fake_trade_invoice", "gambling_updown_score", "gift_card_cashout",
                     "borrow_passbook_clean", "company_shell_transfer",
                     "cross_border_smurfing", "refund_cycle_wash", "commission_layering", "help_move_fund_fee"],
    },
    "theft_robbery_property_crime": {
        "name": "盗窃/抢劫/侵财",
        "subtypes": ["fence_stolen_goods", "insider_stocktip_theft", "courier_intercept",
                     "key_copy_burglary", "atm_skim_team", "snatch_divide_role",
                     "electric_bike_resale_chain", "warehouse_insider_out",
                     "phone_reset_resell", "package_porch_pickup", "parking_lot_breakin", "delivery_fraud_returns"],
    },
    "coercion_blackmail": {
        "name": "胁迫/敲诈",
        "subtypes": ["intimate_photo_extort", "secret_affair_blackmail",
                     "workplace_wrongdoing_leverage", "game_skin_scam_extort_minor",
                     "debt_note_forced", "naked_chat_recording", "trade_secret_threat",
                     "victim_silence_fee", "competitor_sabotage_threat", "fake_pregnancy_claim",
                     "video_call_screen_cap", "agent_debt_bodily_collateral"],
    },
    "other_illicit_coordination": {
        "name": "其他违法协同",
        "subtypes": ["exam_cheating_org", "ticket_scalp_bot", "illegal_lottery_chain",
                     "illegal_fundraising", "unlicensed_medical_practice",
                     "illegal_construction_bribe_inspect", "forest_poaching",
                     "illegal_dumping_fee", "false_invoicing_group", "school_zone_hukou_trade",
                     "fake_marriage_benefit", "rating_farm_order"],
    },
}

# (subtype, roles, latent_facts, observable_signals, benign_confusions, risks)
ARCHETYPES = {
"fraud_scam": [
    ("trust_building_progression", ["scammer", "target"], ["建立信任后引入资金要求", "收益承诺不可兑现", "小额返利诱大额"], ["小额返利按时到账", "话题从闲聊转入投资", "催促限时名额"], ["真实朋友帮忙理财", "合法小额借贷"], [2, 3]),
    ("investment_lead", ["insider", "friend_of_friend"], ["内幕/漏洞投资为虚构", "拉人头分成"], ["晒虚假收益截图", "劝加大投入", "拉第三方进场"], ["合法私募介绍", "正规理财推荐"], [2, 3]),
    ("impersonation", ["impostor", "victim_contact"], ["冒充熟人/客服身份", "制造紧急事由要钱"], ["新号自称老友", "催促马上转账", "拒绝语音核实"], ["真人换号通知", "正规客服回访"], [2, 3]),
    ("refund_deposit_bait", ["fake_customer_service", "consumer"], ["以退款名义骗押金", "先收手续费"], ["准确报出订单信息", "要求屏幕共享", "引导到外部链接"], ["真实平台退款流程", "商家主动补偿"], [2, 3]),
    ("part_time_task", ["task_publisher", "gig_worker"], ["刷单返利为骗局", "垫资后失联"], ["首单小额秒返", "要求连单垫付", "群内托儿晒收益"], ["正规众包平台接单", "朋友介绍兼职"], [2, 3]),
    ("loan_fee_bait", ["fake_lender", "borrower"], ["放款前收解冻费", "无资质放贷"], ["不看征信秒批", "先交保证金", "合同为图片无法核实"], ["正规银行贷款流程", "亲友借款"], [2, 3]),
    ("romance_pig_butchering", ["romance_scammer", "lonely_target"], ["情感养成后引入假平台", "杀猪盘"], ["长期嘘寒问暖", "带做「稳赚」投资", "提现受阻要缴费"], ["真实异地恋互助", "合法情感咨询"], [2, 3]),
    ("account_lending", ["card_buyer", "student_target"], ["收购银行卡四件套用于走账", "学生为主要目标"], ["按张收费", "强调无风险", "要求开网银带U盾"], ["帮朋友代收快递", "合法兼职发传单"], [2, 3]),
    ("escort_payment_claim", ["fake_boss", "greedy_middleman"], ["虚构陪同需求骗定金", "中介截留"], ["高额日结陪同费", "先交服装押金", "面试即收费"], ["正规商务礼仪兼职", "会展临时工"], [2, 3]),
    ("prize_fee", ["lottery_scammer", "excited_winner"], ["中奖先缴税/费为诈骗", "伪造公证"], ["官方口吻通知中奖", "要求先转账手续费", "提供假公证书照片"], ["真实平台抽奖", "商场有奖销售"], [2, 3]),
    ("customer_service_reverse", ["fake_airline", "passenger"], ["退改签为由诱导贷款转账", "冒充航司"], ["主动来电称航班取消", "引导下载会议软件", "索要验证码"], ["航司真实退改签", "OTA客服回电"], [2, 3]),
    ("second_hand_deposit_run", ["fake_seller", "buyer"], ["二手平台引流线下骗定金", "收款拉黑"], ["明显低价", "催走微信私下交易", "发假物流单号"], ["真实二手交易", "朋友间转让"], [1, 2]),
],
"bribery_corruption": [
    ("intermediary_payment_after_result", ["beneficiary", "intermediary"], ["付款与审批结果对价", "经由中间人转付", "刻意避开正式渠道"], ["反复询问进度", "结果确认后转账", "叮嘱不要在群里提"], ["合法居间服务费", "垫付工程款归还"], [2, 3]),
    ("consulting_fee_disguise", ["official_relative", "business_owner"], ["以咨询合同包装利益输送", "无实际服务"], ["签空白咨询合同", "按月固定打款", "从不交付咨询成果"], ["真实行业顾问", "专家评审费"], [2, 3]),
    ("gift_card_channel", ["applicant", "gatekeeper"], ["购物卡代替现金送礼", "节点性送礼"], ["节前约见面", "送卡不说面值", "事后短信暗示事情"], ["正常节日人情往来", "公司福利卡"], [1, 2, 3]),
    ("relative_employment_exchange", ["hiring_manager", "candidate_parent"], ["安排就业换取利益", "绕过招聘流程"], ["面试走形式", "入职前家属收款", "档案特殊处理"], ["正常内推", "亲属回避制度内调岗"], [2, 3]),
    ("project_bid_kickback", ["bid_committee_member", "contractor"], ["泄露标底换点数", "按合同额返点"], ["要求带量报价", "指定品牌参数", "中标后深夜转账"], ["合法分包合作", "居间佣金合规申报"], [3]),
    ("regulatory_tip_payment", ["inspector", "violating_owner"], ["检查前通风报信收费", "长期月费"], ["检查前异常电话", "月度固定支出", "整改永远差一点"], ["合规咨询顾问费", "行业协会会费"], [2, 3]),
    ("procurement_price_padding", ["purchaser", "supplier"], ["抬高采购价分成", "验货放水"], ["唯一供应商议价", "发票品名模糊", "验货即过"], ["正常议价采购", "集中采购折扣"], [2, 3]),
    ("promotion_payment", ["candidate", "decision_maker"], ["花钱买职位晋升", "越级暗箱"], ["考核前密会", "晋升名单提前知道", "事成后大额转账"], ["正常人情答谢", "培训学费资助"], [3]),
    ("school_admission_payment", ["parent", "school_insider"], ["择校费变相收取", "指标生名额交易"], ["捐资助学款外现金", "入学名额内部锁定", "收据开成其他名目"], ["合法捐赠助学", "正常转学手续"], [2, 3]),
    ("medical_channel_fee", ["patient_family", "hospital_staff"], ["红包换取床位/手术安排", "点名费私下收"], ["术前递信封", "指定专家加急", "事后感谢费"], ["正常专家门诊挂号", "医院特需服务费"], [2, 3]),
    ("invoice_rebate", ["finance_clerk", "invoice_broker"], ["虚开发票拿点数", "报销套现"], ["大量替票", "按票面点数结算", "税点话术"], ["正常报销单据整理", "差旅平台开票"], [2, 3]),
    ("contract_signature_fee", ["vendor", "section_chief"], ["盖章费/签字费", "验收卡要"], ["验收前谈「辛苦费」", "尾款被压索贿", "问题台账被拿出来说"], ["正常合同尾款催收", "履约保证金扣除"], [2, 3]),
],
"contraband_illicit_trade": [
    ("batch_quantity_pickup", ["supplier", "distributor"], ["分批交付违禁品", "当面验货"], ["只谈数量批次", "老地方交接", "现结不留账"], ["大宗合法批发", "朋友间代购"], [2, 3]),
    ("code_word_catalog", ["seller", "returning_buyer"], ["暗语目录报价", "行话避检"], ["商品名用代称", "报价按「片/条/个」", "问「上次那种还有吗」"], ["行业黑话的正规交易", "游戏道具交易"], [1, 2, 3]),
    ("cross_region_shipping", ["shipper", "receiver"], ["违禁品跨省寄递", "拆分伪装包装"], ["改包装要求", "走不实名渠道", "收货人用化名"], ["正常跨省网购", "土特产邮寄"], [2, 3]),
    ("prescription_diversion", ["patient_agent", "pill_reseller"], ["处方的管制药品转卖", "串收药品"], ["大量收购安眠药类", "按板收购", "医保卡借用"], ["帮忙代买常用药", "亲属间代取药"], [2, 3]),
    ("replica_counterfeit", ["factory_contact", "reseller"], ["高仿货批发分销", "声称正品"], ["一比一复刻话术", "防伪可过扫码", "拿货价按层级"], ["工厂尾单正品", "平替国货推荐"], [1, 2]),
    ("wildlife_trade", ["poacher_contact", "collector"], ["野生动物制品买卖", "活体运输"], ["问「今年货怎么样」", "冰鲜发货", "只在夜间联系"], ["合法养殖食材", "工艺品收藏讨论"], [2, 3]),
    ("tool_weapon_parts", ["parts_seller", "assembler"], ["管制刀具/枪支散件交易", "改装配件"], ["问「能弄到那种东西吗」", "散件分开寄", "当面验贋试"], ["五金工具采购", "模型道具收藏"], [3]),
    ("e_cigarette_illegal_flavor", ["vendor", "shop_owner"], ["销售禁售口味烟弹", "无证渠道进货"], ["新口味到货暗号", "整条拿货更便宜", "不对外摆"], ["合规电子烟经销", "水果味合法市场讨论"], [1, 2]),
    ("exam_leak_material", ["insider", "exam_broker"], ["考前出售真题", "作弊器材"],
     ["「开考前一夜出货」", "按科报价", "订金锁名额"], ["考前辅导资料", "模拟题库购买"], [3]),
    ("sim_card_pool", ["card_broker", "runner"], ["批量实名录卡转卖", "养卡"], ["一天办几张有限制", "按张结钱", "卡主不知用途"], ["公司统一办工作卡", "家庭副卡"], [2, 3]),
    ("fuel_tax_evasion", ["trucker", "cheap_fuel_seller"], ["走私油/勾兑油交易", "流动黑油车"], ["半夜打电话", "按吨报价", "固定高速口交接"], ["私人加油站优惠", "工地内部加油"], [2, 3]),
    ("tobacco_smuggle", ["port_contact", "wholesaler"], ["免税烟走私分销", "整柜进散柜出"], ["问「这条多少」", "仓库看货", "现金结算"], ["免税店代购讨论", "正常卷烟批发"], [2, 3]),
],
"violence_extortion": [
    ("debt_collection_threat", ["collector", "debtor"], ["以暴力威胁催债", "上门恐吓"], ["发家人照片", "说知道孩子学校", "约「当面谈」"], ["正规催收沟通", "法院诉讼通知"], [2, 3]),
    ("protection_fee", ["collector", "shopkeeper"], ["按月收取保护费", "砸店暗示"], ["月初准时问候", "提别家店出事", "兄弟们不易"], ["物业费催缴", "商会会费"], [3]),
    ("gang_intimidation", ["gang_member", "rival"], ["团伙立威恐吓", "划地盘"], ["约架定规则", "带话给对方", "拍视频立规矩"], ["球赛对抗约战", "单位之间竞争"], [3]),
    ("hired_standing_off", ["hirer", "stand_over_man"], ["雇人堵门壮胆", "不动手吓唬"], ["按天结算", "只要站着别说话", "带几个兄弟"], ["活动安保兼职", "婚礼挡酒兄弟"], [2, 3]),
    ("revenge_stalking_plan", ["aggrieved", "helper"], ["跟踪报复前伴侣/仇人", "踩点"], ["要上下班路线", "问几点回家", "拍照发来确认"], ["帮忙搬家盯物流", "走失老人寻人"], [3]),
    ("beat_example_warning", ["boss_hand", "warning_target"], ["杀鸡儆猴式警告", "动手教训"], ["说「给他长长记性」", "约地下车库", "别出人命就行"], ["严格管理谈话", "劳动纠纷调解"], [3]),
    ("territory_warning", ["incumbent", "newcomer"], ["警告新人别抢生意", "砸摊子威胁"], ["这条街的规矩", "明天还来就别怪我", "兄弟多问候"], ["同业竞争摩擦", "市场管理规劝"], [2, 3]),
    ("online mob_doxx_attack", ["instigator", "crowd_helper"], ["组织网暴人肉", "悬赏线索"], ["发动群里冲他", "悬赏线索费", "全家信息挂出来"], ["舆论监督讨论", "维权信息征集"], [2, 3]),
    ("kidnapping_threat_act", ["kidnapper", "family_contact"], ["绑架索赎", "控制人质"], ["孩子在我们手上", "旧币别做记号", "报警就撕票"], ["恶作剧误会导致", "影视桥段讨论"], [3]),
    ("asset_seizure_force", ["strongman", "business_owner"], ["强占资产/店铺", "换锁清人"], ["明天铺子归我", "合同就别找了", "兄弟们搬东西"], ["商业纠纷走法务", "房东正常收铺"], [3]),
    ("witness_intimidation", ["defendant_side", "witness"], ["威胁证人改口", "盯梢"], ["法庭见面打招呼", "孩子放学谁接", "想清楚再说话"], ["律师会见沟通", "证人保护告知"], [3]),
    ("settlement_by_force", ["injured_party_gang", "responsible_party"], ["私了强索高额赔偿", "带人压场"], ["不赔就卸你一条腿", "写个字据按手印", "兄弟们等着吃饭"], ["正常交通事故私了", "保险理赔协商"], [2, 3]),
],
"sexual_transaction_exploitation": [
    ("escort_arrangement", ["client", "arranger"], ["有偿性陪侍安排", "按次计费"], ["问「资源还在吗」", "报身高年龄", "酒店自付"], ["正规商务伴游澄清", "朋友聚会邀约"], [2, 3]),
    ("introductory_middleman", ["middleman", "newcomer"], ["介绍卖淫抽成", "新人入行"], ["带新人见客", "首单抽三成", "规矩要懂"], ["婚介红娘", "夜场合法招聘讨论"], [3]),
    ("platform_referral", ["platform_admin", "invitee"], ["招嫖平台邀请码", "会员分级"], ["发卡片式图", "凭暗号下单", "老客带新有返"], ["交友软件正常邀请", "兴趣社群拉新"], [2, 3]),
    ("photo_material_trade", ["seller", "collector"], ["私密照片材料买卖", "按套计价"], ["样品打码", "素人原创", "过网盘秒发"], ["摄影约拍合作", "情侣间分享"], [3]),
    ("minor_grooming_signal", ["adult", "minor_contact"], ["对未成年人性引诱", "以游戏/礼物接近"], ["问年龄学校后仍继续", "要私密照", "别告诉爸妈"], ["亲戚照看孩子", "兴趣班老师沟通"], [3]),
    ("cam_room_fee_split", ["room_owner", "performer"], ["色情直播分成", "刷礼物返现"], ["晚上十点开播", "礼物五五分", "封号就换群"], ["正规直播公会", "才艺主播合作"], [2, 3]),
    ("hotel_on_site_coordination", ["dispatcher", "girl"], ["上门服务调度", "报房间号"], ["发定位发房号", "十分钟内到", "先款后见"], ["正规酒店客房服务", "同事送文件"], [3]),
    ("long_term_support_exchange", ["sugar_daddy", "dependent"], ["以资助换性关系", "月抛式包养"], ["每月固定转账", "租房报销", "别让正室知道"], ["正常恋爱开销", "助学金资助"], [1, 2, 3]),
    ("model_recruitment_bait", ["recruiter", "aspiring_model"], ["以模特招募引诱", "面试即收费/套图"], ["先交拍摄费", "酒店试镜", "红人之路话术"], ["正规经纪公司面试", "摄影机构合作"], [2, 3]),
    ("overseas_tour_group", ["tour_organizer", "customer"], ["境外色情团", "一价全包"], ["签证打包价", "行程表只有夜市", "老客户优先"], ["出境游团购", "商务考察团"], [3]),
    ("debt_body_exchange", ["creditor", "debtor"], ["以肉偿抵债胁迫", "拿把柄压人"], ["没钱就用别的还", "每次抵两千", "照片我都留着"], ["分期还款协商", "劳动抵偿合法约定"], [3]),
    ("live_stream_reward_launder", ["guilder", "streamer"], ["打赏洗钱通道", "刷量返现"], ["大额礼物秒退", "对公走账", "税点另算"], ["正常直播打赏", "公会刷量灰色讨论"], [2]),
],
"privacy_doxxing": [
    ("id_address_lookup", ["buyer", "data_seller"], ["付费查询身份证地址", "开房记录"], ["给手机号查身份", "按条计费", "秒出结果"], ["律师依法调证", "平台实名核验讨论"], [2, 3]),
    ("phone_number_trace", ["stalker", "service_provider"], ["定位他人手机", "实时轨迹"], ["只要大概位置", "按周付费", "别用于违法"], ["家长监护定位", "公司车辆调度"], [3]),
    ("travel_record_query", ["jealous_partner", "insider"], ["查航班/酒店同住记录", "行程泄露"], ["查他这几天住哪", "和谁一起登机", "内部系统截图"], ["票务代理正常查询", "秘书安排行程"], [2, 3]),
    ("family_info_dump", ["harasser", "info_broker"], ["打包他人全家信息", "用于骚扰"], ["学校班级都查好", "老人的病 histories", "打包价更划算"], ["家谱整理", "背景调查公司"], [3]),
    ("social_thread_expose", ["forum_user", "moderator_bypass"], ["扒社交账号关联", "匿名账号破功"], ["小号也给你翻了", "相册原图时间", "转发过什么都能查"], ["公开信息检索讨论", "品牌舆情分析"], [1, 2]),
    ("workplace_contact_out", ["poacher", "assistant"], ["出售同事联系方式", "简历库倒卖"], ["整个部门电话", "简历按份卖", "离职名单"], ["猎头正常触达", "通讯录共享授权"], [1, 2]),
    ("medical_record_browse", ["curious_party", "clinic_staff"], ["查询他人就诊记录", "病情泄露"], ["帮他查下化验单", "系统里点一下", "发红包了"], ["陪诊代取报告授权", "保险核保流程"], [2]),
    ("purchase_data_resell", ["merchant_staff", "data_reseller"], ["客户订单信息倒卖", "精准诈骗数据"], ["新单当天出货", "含电话地址", "按城市打包"], ["会员营销合规共享", "数据合作脱敏讨论"], [2, 3]),
    ("location_share_tracking", ["controller", "tracked_person"], ["偷偷装定位", "车轮定位器"], ["磁吸的免接线", "一周一换车", "手机也帮他装一个"], ["家庭共享位置", "车队管理"], [3]),
    ("chat_log_export", ["hacker_for_hire", "client"], ["导出他人聊天记录", "云备份窃取"], ["只要微信记录", "安卓苹果都能搞", "按月导"], ["自己手机数据恢复", "企业合规审计"], [3]),
    ("face_search", ["searcher", "face_db_seller"], ["以图搜人查身份", "摄像头库"], ["一张侧脸就够", "全城摄像头扫", "出结果付费"], ["安防行业讨论", "失联亲友寻人报警"], [2, 3]),
    ("courier_info_leak", ["courier_staff", "scam_lead_seller"], ["快递单信息出售", "面单照片"], ["当天新单截图", "含电话住址", "四块一条"], ["快递理赔核实", "驿站正常登记"], [2]),
],
"money_laundering_obfuscation": [
    ("card_four_piece_pool", ["card_collector", "student_supplier"], ["收卡走账", "四件套按张收"], ["日结五百", "额度越大越好", "人卡合影"], ["废品回收创业讨论", "银行卡办卡优惠"], [3]),
    ("split_transfer_chain", ["dispatcher", "runner"], ["大额拆分转账", "跑分接力"], ["一笔拆二十个", "到账就转出去", "佣金千分之五"], ["正常批量付款", "群收款分账"], [3]),
    ("crypto_offramp", ["otc_desk", "cash_provider"], ["USDT 换现金", "汇率暗点"], ["周三交U周五给现", "当面点钞", "汇率好过交易所"], ["合法持牌交易", "币圈出金讨论"], [2, 3]),
    ("fake_trade_invoice", ["issuer", "buyer"], ["虚开增值税票抵账", "资金回流"], ["合同货单资金三流一致", "点数八个", "受票方可靠"], ["正常税务筹划", "供应链开票"], [3]),
    ("gambling_updown_score", ["upline", "downline"], ["赌博平台上下分", "代充代提"], ["第七层通道", "佣金千八", "秒结"], ["游戏点券代充", "平台充值服务"], [3]),
    ("gift_card_cashout", ["casher", "card_source"], ["购物卡快速变现", "折价回收"], ["九四折实结", "京东卡苏果卡都要", "卡密即付"], ["正规卡券回收平台", "公司福利卡转让"], [1, 2, 3]),
    ("borrow_passbook_clean", ["fund_holder", "passbook_lender"], ["借存折过流水", "报酬按天"], ["放你卡里过一夜", "抽千分之三", "征信不影响"], ["帮忙代收货款", "亲属账户周转"], [2, 3]),
    ("company_shell_transfer", ["shell_seller", "operator"], ["买卖空壳对公账户", "过户即用"], ["带对公带章", "开通网银额度", "法人变更包过"], ["公司转让正常流程", "代办执照服务"], [3]),
    ("cross_border_smurfing", ["smurf_boss", "courier"], ["蚂蚁搬家换汇", "口岸现钞"], ["一人一天两万额度", "往返八次", "每次多带点"], ["合理换汇额度使用", "留学缴学费"], [3]),
    ("refund_cycle_wash", ["merchant", "accomplice"], ["虚假退款洗资金", "退款进不同卡"], ["原路退回指定卡", "手续费两个点", "流水好看"], ["正常电商退款", "刷单退款纠纷讨论"], [2, 3]),
    ("commission_layering", ["agency_boss", "nominee"], ["多层代理层层走账", "截留分成"], ["合同走A打款给B", "居间协议备好", "税点你们出"], ["多层合法分销", "代理记账服务"], [1, 2]),
    ("help_move_fund_fee", ["recruiter", "innocent_looking_runner"], ["雇人取现跑腿洗钱", "用清洁工/学生"], ["取现拿千分之五", "带身份证就行", "当天往返"], ["帮忙取快递", "兼职跑腿平台"], [3]),
],
"theft_robbery_property_crime": [
    ("fence_stolen_goods", ["thief", "fence"], ["销赃渠道长期合作", "低于市价三成"], ["昨晚货到", "验货不问来路", "老价格"], ["二手回收商", "闲置转让"], [2, 3]),
    ("insider_stocktip_theft", ["warehouse_staff", "outside_boss"], ["内盗出货", "监控避开"], ["周三盘点前", "西门没监控", "按件结"], ["仓库 Normal 出货", "库存调拨"], [2, 3]),
    ("courier_intercept", ["insider_courier", "reseller"], ["截获贵重快递", "扫码入自己袋"], ["苹果手机专线", "丢件率我来控", "赔付有公司"], ["快递正常派送", "驿站代收"], [2, 3]),
    ("key_copy_burglary", ["locksmith", "burglar"], ["配钥匙踩点入室", "只拿现金"], ["那种老小区最好开", "傍晚五点半", "只去一次"], ["正规开锁换锁", "物业钥匙管理"], [3]),
    ("atm_skim_team", ["tech_guy", "lookout"], ["ATM 装置窃取", "分工踩点"], ["读卡器到了", "算好取款高峰", "装备分两批"], ["银行设备巡检", "金融安防讨论"], [3]),
    ("snatch_divide_role", ["rider", "pillion"], ["飞车抢夺分工", "路线规划"], ["你骑车我下手", "天桥下加速", "当晚会金"], ["摩的载客", "骑行俱乐部"], [3]),
    ("electric_bike_resale_chain", ["thief", "reseller"], ["偷电瓶车转卖", "套牌改架号"], ["新车三天出", "架子磨掉重打", "带牌更贵"], ["二手电动车交易", "车辆过户流程"], [2, 3]),
    ("warehouse_insider_out", ["night_guard", "organized_buyer"], ["夜班守卫内应", "整车拉货"], ["周三夜班我值", "卷帘门留缝", "一车一万"], ["夜班值守调货", "正常大宗出货"], [3]),
    ("phone_reset_resell", ["picker", "unlocker"], ["捡偷手机解锁转卖", "刷机洗白"], ["有锁的便宜出", "ID能硬解", "批量来更优惠"], ["二手手机回收", "失物招领"], [1, 2]),
    ("package_porch_pickup", ["spotter", "pickup_runner"], ["蹲点偷快递", "尾随进门"], ["小区快递架没人看", "双十一最好干", "按件给钱"], ["帮忙代拿快递", "驿站自提"], [1, 2]),
    ("parking_lot_breakin", ["scanner", "opener"], ["停车场砸窗盗窃", "专挑包在车内"], ["感应器三秒开", "商场B2最多", "只拿包不碰车"], ["开锁救援服务", "停车场管理讨论"], [2, 3]),
    ("delivery_fraud_returns", ["returner", "refunder"], ["掉包退货骗差价", "假货换真货"], ["原包装膜我有", "售后只看码", "一单赚一千"], ["正常七天无理由", "瑕疵退货协商"], [1, 2]),
],
"coercion_blackmail": [
    ("intimate_photo_extort", ["blackmailer", "victim"], ["私密照勒索", "论坛公开威胁"], ["照片在我这", "今晚十二点前", "发了你单位群"], ["情侣间玩笑", "误发照片道歉"], [3]),
    ("secret_affair_blackmail", ["knower", "married_official"], ["婚外情敲诈", "长期月供"], ["嫂子知道这事吗", "每月八号", "照顾好你自己"], ["情感纠纷协商", "离婚律师函"], [3]),
    ("workplace_wrongdoing_leverage", ["whistleblower_turned_extorter", "executive"], ["拿违纪把柄要挟", "封口费"], ["我留了底", "升我职这事就算了", "不然审计见"], ["合法举报讨论", "劳动仲裁"], [2, 3]),
    ("game_skin_scam_extort_minor", ["older_peer", "minor_victim"], ["以游戏交易吓唬未成年人", "索要家长手机"], ["你涉嫌犯罪了", "拿你爸妈手机来", "报警你就完了"], ["游戏交易纠纷", "家长监护沟通"], [3]),
    ("debt_note_forced", ["loan_shark", "borrower"], ["逼签超额借条", "空白手印"], ["利息你不用管先签", "房子抵押写上", "不签今天出不去"], ["正规借条签订", "担保公司流程"], [3]),
    ("naked_chat_recording", ["recruiter", "victim"], ["裸聊录屏勒索", "秒删为饵"], ["录屏了", "先转两千", "通讯录我都拿到了"], ["网恋视频误会", "隐私泄露维权"], [3]),
    ("trade_secret_threat", ["departing_employee", "employer"], ["以泄密威胁索取", "源码在手"], ["代码我都拷了", "竞业赔偿免了", "不然发对手邮箱"], ["离职交接谈判", "技术方案转让"], [2, 3]),
    ("victim_silence_fee", ["perpetrator_side", "victim"], ["要受害者封口", "一次了断"], ["这事对你名声不好", "五万一次清", "别闹大对你没好处"], ["侵权赔偿和解", "人身损害调解"], [3]),
    ("competitor_sabotage_threat", ["saboteur", "shop_owner"], ["扬言破坏经营勒索", "泼漆预告"], ["隔壁奶茶店你知道的", "每月三千平安", "明天见分晓"], ["商业竞争摩擦", "物业纠纷"], [3]),
    ("fake_pregnancy_claim", ["claimant", "man"], ["假孕/假亲子勒索", "验假报告"], ["报告单我找人做的", "每月抚养费", "不认就闹到你单位"], ["真实亲子纠纷", "抚养费诉讼"], [2, 3]),
    ("video_call_screen_cap", ["catfisher", "victim"], ["视频裸聊截屏群发威胁", "通讯录轰炸"], ["你的名单在我这", "先来个八千", "分钟级倒计时"], ["视频聊天误会", "诈骗预警提醒"], [3]),
    ("agent_debt_bodily_collateral", ["gang_lender", "desperate_borrower"], ["以扣人抵债", "控制自由"], ["人先跟我们走", "还清来接", "吃住我们管"], ["正常担保借贷", "工地扣证件纠纷讨论"], [3]),
],
"other_illicit_coordination": [
    ("exam_cheating_org", ["organizer", "proctor_inside"], ["考试作弊团伙", "内应传答案"], ["设备已升级", "按科收费", "考场里戴耳环那个"], ["考前辅导机构", "模拟考组织"], [3]),
    ("ticket_scalp_bot", ["script_writer", "scalper"], ["抢票外挂分销", "代抢加价"], ["加速包参数调好", "成功一张三百", "实名问题我来搞"], ["候补购票技巧", "正规代购"], [1, 2]),
    ("illegal_lottery_chain", ["station_owner", "collector"], ["地下六合彩收单", "层级坐庄"], ["今晚开什么", "吃退水两个点", "外围就找你"], ["体彩店讨论", "彩票合买"], [3]),
    ("illegal_fundraising", ["promoter", "investor_rel"], ["非法集资拉存款", "高息承诺"], ["月息三分保本", "拉一个返两个点", " только现金"], ["银行理财推荐", "正规众筹"], [2, 3]),
    ("unlicensed_medical_practice", ["quack", "referring_friend"], ["无证行医接诊", "熟人介绍"], ["打针的事别外传", "诊所不留记录", "出事你不知道我"], ["正规医生私下咨询", "理疗保健讨论"], [2, 3]),
    ("illegal_construction_bribe_inspect", ["builder", "chenguan_contact"], ["违建免拆打点", "检查前消息"], ["加层的事稳了", "年前不会来查", "烟酒照旧"], ["正规报建流程", "物业装修管理"], [2, 3]),
    ("forest_poaching", ["trapper", "buyer"], ["盗猎野味供应", "套子下山的货"], ["「这个月只有四只」", "冰袋备好", "夜里两点交"], ["山货土产收购", "养殖野味合法讨论"], [2, 3]),
    ("illegal_dumping_fee", ["factory_boss", "trucker"], ["偷倒工业废料", "按车付费"], ["晚上十二点老地方", "一车一千五", "别倒在以前那片"], ["正规危废处置", "渣土运输"], [2, 3]),
    ("false_invoicing_group", ["invoice_boss", "accountant"], ["虚开团伙分工", "资金回流闭环"], ["这月票量不够", "资金流截图做好", "税务稽查名单外"], ["代账公司开票", "税务筹划讨论"], [3]),
    ("school_zone_hukou_trade", ["agent", "transfer_parent"], ["户口挂靠择校", "指标名额买卖"], ["挂户两年就行", "费用二十个", "校长那边通了"], ["学区房正常购买", "积分入学政策"], [2, 3]),
    ("fake_marriage_benefit", ["fake_couple", "agent"], ["假结婚过户指标", "拆迁分户"], ["领证费八万", "拆迁前不离婚", "协议写清楚"], ["婚介服务", "婚姻财产咨询"], [2, 3]),
    ("rating_farm_order", ["farm_boss", "account_supplier"], ["刷单控评水军", "账号群控"], ["一百个号今晚开工", "文案我发你", "号商欠我货"], ["营销推广讨论", "UGC运营"], [1, 2]),
],
}



# 补充批次（凑足 >=150；与主表合并）
EXTRA = {
"fraud_scam": [
    ("loan_bridge_interest_rollover", ["bridge_lender", "borrower"], ["以过桥为名收砍头息", "利滚利吞房"], ["先扣两个月利息", "到期让你再借一家还这家"], ["正常过桥资金", "亲友应急借款"], [2, 3]),
    ("inner_job_purchase", ["job_agent", "parent"], ["花钱买编制岗位", "指标内部消化"], ["名额就剩一个", "先交后签", "笔试走过场"], ["正规人才引进", "事业单位公开招聘"], [2, 3]),
    ("video_coaching_parent_scam", ["fake_coach", "worried_parent"], ["以辅导孩子为名骗课时费", "资质造假"], ["清华退学名师", "十节包提分", "最后三个名额"], ["真实在线教育", "大学生家教"], [1, 2]),
    ("camera_sd_recovery_fraud", ["repair_seller", "victim"], ["以修相机为名窃取素材", "用素材施压"], ["卡里的照片我帮你恢复了", "这些内容很有意思吧"], ["正规数据恢复", "婚庆摄影交付"], [2, 3]),
],
"contraband_illicit_trade": [
    ("medicine_crossborder_resale", ["daigou", "group_buyer"], ["绕开审批进口药品转卖", "朋友圈囤药"], ["原研版比医院便宜", "整盒拿更划算", "冷链我包"], ["正规海外代购药品咨询", "药店促销"], [1, 2]),
    ("shell_chemical_diversion", ["chemical_seller", "middleman"], ["易制毒化学品流入非标渠道", "改用途开票"], ["桶上贴别的标签", "别问用途", "现金自提"], ["正规化工原料采购", "实验室试剂供应"], [3]),
    ("alcohol_counterfeit_line", ["bottler", "restaurant_supplier"], ["名酒灌装假冒", "回收瓶翻新"], ["瓶子你出", "防伪码能过", "夜场专供"], ["正规名酒经销", "散酒作坊讨论"], [2]),
],
"violence_extortion": [
    ("fee_skimming_site_riot", ["site_boss", "laborer_leader"], ["工地堵门要钱带恐吓", "组织围堵"], ["把大门堵上", "把横幅拉起来", "不动手但人要多"], ["合法讨薪", "劳动监察投诉"], [2]),
    ("campus_periphery_intimidation", ["older_student", "younger_student"], ["校门口收学生保护费", "长期小额"], ["每天十块", "不交你知道后果", "别告诉老师"], ["同学间借钱", "小卖部赊账"], [3]),
    ("livestream_hate_raid_for_hire", ["client", "raid_organizer"], ["雇人网暴直播商家", "组织差评轰炸"], ["一单五十冲十分钟", "话术我发你", "换号继续"], ["差评维权", "营销互喷讨论"], [2]),
],
"sexual_transaction_exploitation": [
    ("night_club_female_recruit", ["talent_scout", "student"], ["夜场以高薪诱骗女学生", "去哪不明"], ["日结八百只陪客户唱歌", "买衣服的钱公司先垫", "别带手机进场"], ["正规夜场演出招募", "酒水促销兼职"], [2, 3]),
    ("photographer_private_pressure", ["photographer", "young_model"], ["以资源胁迫约拍私密", "职业门槛施压"], ["想红就别矫情", "这组只有我能拍", "不拍资源断了"], ["正规艺术约拍", "经纪公司试镜"], [2, 3]),
    ("dorm_introduction_network", ["senior", "freshman"], ["在校生介绍链条", "兼职包装"], ["晚上陪酒一场三百", "学姐带你", "别在宿舍说"], ["正规兼职群", "社团活动"], [3]),
    ("rehab_house_pimping", ["inside_contact", "outsider_middleman"], ["所内拉皮中介", "家属渠道"], ["里面的人也要消费", "你递话我给钱", "别带手机"], ["正常家属会见沟通", "所内小卖部"], [3]),
],
"privacy_doxxing": [
    ("exam_score_lookup", ["parent_agent", "school_staff"], ["查他人成绩档案", "升学信息泄露"], ["班主任系统点一下", "红包已发", "截图就行"], ["家长查自己孩子", "学校官方查询"], [1, 2]),
    ("insurance_claims_snoop", ["adjuster_side", "clinic_contact"], ["买通查询他人理赔就诊", "定损压价筹码"], ["把病历调出来", "这条信息值一顿饭", "别走系统"], ["保险正常理赔调查", "公估公司流程"], [2]),
    ("hotel_register_leak", ["front_desk", "tracker"], ["住宿登记信息外卖", "同住人查询"], ["刚入住就出单", "按次结", "只在夜班"], ["前台正常入住登记", "警方依法查询"], [3]),
],
"money_laundering_obfuscation": [
    ("phone_topup_layering", ["shop_owner", "runner"], ["话费充值小店走量洗钱", "批量代充"], ["一天几十单不问人", "上游给我充值卡密", "利润两个点"], ["正规充值代理", "便利店代缴业务"], [2, 3]),
    ("cross_shop_pos_machine", ["pos_broker", "merchant"], ["POS机套现串店", "虚假刷卡"], ["机器放你店里刷", "流水我做", "费率给你优惠"], ["正规收单服务", "信用卡正常消费"], [2, 3]),
    ("charity_receipt_wash", ["foundation_contact", "donor"], ["慈善捐赠回流返点", "假捐发票"], ["捐十万返八万五", "发票全额开", "走对公好看"], ["合法公益捐赠抵税", "基金会募捐"], [3]),
],
"theft_robbery_property_crime": [
    ("farm_irrigation_motor_theft", ["night_crew", "scrap_buyer"], ["偷灌溉电机卖废品", "农村无人时下手"], ["浇完地就收", "铜价现在高", "村口狗多绕后"], ["废品正常回收", "农机维修"], [2]),
    ("construction_site_material_out", ["site_worker", "material_trader"], ["工地钢材水泥外运", "门禁内应"], ["下班车斗帆布盖", "按吨算", "保安我搞定"], ["工地退场材料处理", "正规废料清运"], [2, 3]),
    ("shared_bike_parts_strip", ["stripper", "parts_seller"], ["拆共享单车零件卖", "批量剥离"], ["一晚上二十辆", "只要锁和变速", "拆完扔河里"], ["共享单车运维", "旧货市场"], [1, 2]),
],
"coercion_blackmail": [
    ("courier_claim_extort", ["claimant", "courier_station"], ["以投诉勒索站点", "恶意索赔"], ["不赔我就发抖音", "媒体朋友一堆", "一个投诉扣你半月"], ["正常快递理赔", "消费维权"], [2]),
    ("resident_noise_leverage", ["troublemaker", "upstairs_neighbor"], ["以举报扰民勒索好处", "长期吃拿"], ["每月两条烟这事就平", "我认识城管", "抬头不见低头见"], ["邻里噪音调解", "物业投诉流程"], [1, 2]),
    ("employer_record_threat", ["ex_accountant", "boss"], ["以账目问题威胁前雇主", "离职报复"], ["账我都有底", "监察和税务我都能寄", "补偿到位就删"], ["合法劳动仲裁", "财务交接异议"], [2, 3]),
],
"other_illicit_coordination": [
    ("homework_ghostwriting_ring", ["agent", "writer_pool"], ["论文代写产业化", "学籍造假"], ["查重我保过", "一篇一千五", "导师那边我打招呼"], ["写作辅导服务", "论文润色"], [1, 2]),
    ("residency_quota_trade", ["middleman", "graduate_family"], ["进京/落户指标买卖", "档案造假"], ["指标只有两个", "社保挂靠一年", "办不成全退"], ["人才引进代办", "积分落户咨询"], [2, 3]),
    ("informal_loan_ads_network", ["ads_boss", "poster"], ["违法小广告链条", "贷款中介引流"], ["一夜贴完一个区", "按栋结钱", "撕了扣钱"], ["正规广告投放", "社区通知张贴"], [1]),
    ("prepaid_card_pony_layer", ["card_king", "student_runner"], ["预付卡非法套现组织", "校园代理"], ["办卡就返现", "拉一人提成八十", "别用自己身份证"], ["正规校园卡服务", "消费券活动"], [2]),
],
}


def build():
    tax_out = {}
    n_arc = 0
    lines = []
    for cat, meta in TAXONOMY.items():
        arch = ARCHETYPES[cat] + EXTRA.get(cat, [])
        tax_out[cat] = {"name": meta["name"], "subtypes": [s for s, *_ in arch]}
        for i, (subtype, roles, facts, signals, confusions, risks) in enumerate(arch, 1):
            n_arc += 1
            lines.append(json.dumps({
                "archetype_id": f"ARC-{n_arc:06d}",
                "top_category": cat,
                "subtype": subtype,
                "roles": [r.strip() for r in roles],
                "latent_facts": facts,
                "observable_signals": signals,
                "benign_confusions": confusions,
                "allowed_risk_levels": risks,
                "safety_constraints": {
                    "no_operational_crime_instructions": True,
                    "no_real_personal_data": True,
                    "no_real_account_numbers": True,
                },
            }, ensure_ascii=False))
    (ROOT / "taxonomy" / "business_taxonomy_v1.json").write_text(
        json.dumps({"schema_version": "BUSINESS-TAXONOMY-v1",
                    "top_categories": tax_out}, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "archetypes" / "archetypes.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"taxonomy: {len(tax_out)} categories; archetypes: {n_arc}")


if __name__ == "__main__":
    build()
