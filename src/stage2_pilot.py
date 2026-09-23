# -*- coding: utf-8 -*-
"""Pilot batch: 6 cases authored per PRM-DIALOGUE-001 (session model as generator),
registered through stage2_pipeline (program acceptance + registry + YAML)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stage2_pipeline as P  # noqa: E402


def M(t, s, x):
    return {"type": "message", "time": t, "speaker": s, "text": x}


def T(t, f, to, amount):
    return {"type": "transfer", "time": t, "from": f, "to": to, "amount": amount,
            "status": "received"}


def case_common(identity, labels, hidden, attr, sig, events, title, lineage=None):
    return {
        "identity": identity,
        "source": {"source_ids": ["SRC-SYN-001"], "source_type": "synthetic_pilot"},
        "lineage": lineage or {"root_case_id": None, "parent_case_id": None,
                               "generation_type": "original"},
        "labels": labels,
        "hidden_case": hidden,
        "attributes": attr,
        "generation_signature": sig,
        "execution": {"prompt_id": "PRM-DIALOGUE-001", "agent_id": "AGT-SESSION-001",
                      "model_id": "MOD-SESSION-001", "batch_id": "BATCH-PILOT-001"},
        "dedup": {},
        "title": title,
        "events": events,
    }


# ---------------- CASE A: bribery risk3 (医院设备采购，中间人转付) ----------------
EV_A = [
    M("10月8日 09:12", "A", "张科，早。上次说的那台CT还是这个型号吗？"),
    M("10月8日 09:20", "B", "型号没变，预算还在走流程。"),
    M("10月8日 09:22", "A", "大概什么时候能有准信？厂里催我报价。"),
    M("10月8日 09:25", "B", "急不来，牵扯的人多。"),
    M("10月8日 09:26", "A", "懂，那我不催。"),
    M("10月8日 12:40", "B", "中午吃啥，食堂还是外面？"),
    M("10月8日 12:41", "A", "外面，新开的那家面馆走一个。"),
    M("10月8日 12:55", "B", "这家的牛肉面还行。"),
    M("10月8日 12:56", "A", "下次带你尝尝他们家的小菜。"),
    M("10月9日 10:03", "A", "王老师家的孩子病好了吗？"),
    M("10月9日 10:05", "B", "好了，昨天返校。"),
    M("10月9日 10:06", "A", "那就好。对了，参数这块还需要我配合什么吗？"),
    M("10月9日 10:08", "B", "标书你按我发你的那份改，别自作主张。"),
    M("10月9日 10:09", "A", "明白，都照你说的来。"),
    M("10月9日 19:30", "B", "今晚有球，看吗？"),
    M("10月9日 19:31", "A", "看，老地方？"),
    M("10月9日 19:32", "B", "嗯。"),
    M("10月10日 08:50", "A", "昨晚那个点球争议大了。"),
    M("10月10日 08:52", "B", "VAR就该取消，看得气死。"),
    M("10月10日 08:53", "A", "哈哈。对了，评审名单定了吗？"),
    M("10月10日 08:56", "B", "差不多，还是那几位。"),
    M("10月10日 08:57", "A", "那就稳了吧？"),
    M("10月10日 08:59", "B", "别问这么直白。等通知。"),
    M("10月10日 14:22", "A", "媳妇让我问你这周末去不去摘橘子。"),
    M("10月10日 14:24", "B", "去，孩子们正好放假。"),
    M("10月11日 09:40", "A", "今天出结果吗？"),
    M("10月11日 09:41", "B", "下午签。"),
    M("10月11日 09:42", "A", "那台机器的售后我还是指定老刘团队，行不行？"),
    M("10月11日 09:44", "B", "可以，这个你定。"),
    M("10月11日 15:10", "B", "签了。"),
    M("10月11日 15:11", "A", "好。还是上次说的那个数？"),
    M("10月11日 15:12", "B", "对。你别直接找他，我这边来。"),
    M("10月11日 15:13", "A", "明白，只跟你对接。"),
    T("10月11日 15:40", "A", "B", 40000),
    M("10月11日 15:41", "B", "收到。"),
    M("10月11日 15:42", "A", "剩下的一半验收后给。"),
    M("10月11日 15:43", "B", "行。这事不要在项目群里提。"),
    M("10月11日 15:44", "A", "放心，我一个字没说过。"),
    M("10月12日 10:15", "A", "橘子我订了两箱，周末给你带一箱。"),
    M("10月12日 10:16", "B", "客气啥，人过来就行。"),
    M("10月12日 16:02", "B", "老刘那边你让他下周进场装。"),
    M("10月12日 16:03", "A", "好，我通知他。"),
    M("10月13日 09:30", "A", "张科，验收大概什么节奏？"),
    M("10月13日 09:32", "B", "装机完跑两周，月底验收。"),
    M("10月13日 09:33", "A", "那月底我按老规矩办。"),
    M("10月13日 09:34", "B", "嗯。先不聊这个，开会上楼了。"),
    M("10月14日 20:05", "A", "周末摘橘子带娃去，你们家那位来不来？"),
    M("10月14日 20:07", "B", "她值班，我和孩子来。"),
    M("10月14日 20:08", "A", "行，周日早上九点园子门口。"),
]
CASE_A = case_common(
    identity={"family_id": "FAM-PILOT-0001", "lineage_id": "LIN-PILOT-0001",
              "archetype_id": "ARC-000009", "variant_id": "v01"},
    labels={"risk": 3, "category": "bribery_corruption", "illicit_likelihood": 3,
            "evidence_strength": "strong", "review_required": True},
    hidden={"latent_intent": "设备采购中标后向评审关键人支付回扣，经中间人转付并刻意避人耳目。",
            "critical_evidence": ["中标前多次打探进度并强调照办", "中标当日即向中间人大额转账",
                                  "明确说别直接找他、别在项目群里提", "约定剩余部分验收后支付"],
            "benign_alternatives": ["合法居间服务费", "设备售后协调费"]},
    attr={"duration_days": 7, "turn_count": 48, "relationship": "business",
          "obfuscation": "high", "has_transfer": True, "normal_transfer_count": 0,
          "suspicious_transfer_count": 1},
    sig={"subtype": "intermediary_payment_after_result"},
    events=EV_A,
    title="利益输送：设备中标当日经中间人转付回扣")

# ---------------- CASE A' sibling: 同骨架，资金=正规居间服务费 (risk0) ----------------
EV_A2 = [dict(e) for e in EV_A]
for e in EV_A2:
    if e["type"] == "message" and e["text"] == "好。还是上次说的那个数？":
        e["text"] = "好。咨询费按合同那个数走？"
    if e["type"] == "message" and e["text"] == "对。你别直接找他，我这边来。":
        e["text"] = "对，合同价，你直接对公转我们公司就行。"
    if e["type"] == "message" and e["text"] == "明白，只跟你对接。":
        e["text"] = "行，发票我让财务一起开好。"
    if e["type"] == "message" and e["text"] == "行。这事不要在项目群里提。":
        e["text"] = "行，合同归档后我在项目群里发个复函。"
    if e["type"] == "message" and e["text"] == "那月底我按老规矩办。":
        e["text"] = "那月底验收单我提前准备。"
    if e["type"] == "message" and e["text"] == "剩下的一半验收后给。":
        e["text"] = "尾款按合同验收后付。"
CASE_A2 = case_common(
    identity={"family_id": "FAM-PILOT-0001", "lineage_id": "LIN-PILOT-0001",
              "archetype_id": "ARC-000009", "variant_id": "v02"},
    labels={"risk": 0, "category": "none", "illicit_likelihood": 0,
            "evidence_strength": "strong", "review_required": False},
    hidden={"latent_intent": "经销商向持证咨询公司支付合法市场询价与标书咨询服务费，流程留痕。",
            "critical_evidence": ["明确按合同对公支付并开发票", "群里发复函、合同归档留痕", "无隐藏指令"],
            "benign_alternatives": ["正常居间咨询费", "合规采购辅助服务"]},
    attr={"duration_days": 7, "turn_count": 48, "relationship": "business",
          "obfuscation": "low", "has_transfer": True, "normal_transfer_count": 1,
          "suspicious_transfer_count": 0},
    sig={"subtype": "intermediary_payment_after_result"},
    events=EV_A2,
    title="正常采购咨询：居间服务费对公结算",
    lineage={"root_case_id": None, "parent_case_id": None,
             "generation_type": "contrastive_sibling"})

# ---------------- CASE B: fraud part_time_task risk2 (刷单垫付) ----------------
EV_B = [
    M("11月3日 20:11", "A", "姐妹，进群了？今天的单子看了吗"),
    M("11月3日 20:12", "B", "进了，看着有点复杂"),
    M("11月3日 20:13", "A", "超简单，拍下付款截图发我，本金加佣金马上返你"),
    M("11月3日 20:14", "B", "真返啊？"),
    M("11月3日 20:15", "A", "我做了三个月了，你看群里的晒单"),
    M("11月3日 20:30", "B", "我先试个小额的"),
    M("11月3日 20:41", "A", "收到，108 返你 118，看下微信"),
    T("11月3日 20:41", "A", "B", 118),
    M("11月3日 20:42", "B", "到了到了，这么快"),
    M("11月3日 21:00", "B", "宝宝睡了才腾出空，还有单吗"),
    M("11月3日 21:01", "A", "今晚大单，垫付 2000 返 260，做不做"),
    M("11月3日 21:02", "B", "这么大？"),
    M("11月3日 21:03", "A", "名额就两个，做完今天封顶"),
    M("11月3日 21:05", "B", "那…我做"),
    T("11月3日 21:18", "B", "A", 2000),
    M("11月3日 21:20", "A", "收到。这个是连单，要把第二单也做完才能一起返"),
    M("11月3日 21:21", "B", "啊？还要再做？"),
    M("11月3日 21:22", "A", "系统卡任务，别慌，做完这单 2000 的全返"),
    M("11月3日 21:40", "B", "转了，这次真到账了吧"),
    M("11月3日 21:41", "A", "在处理，急单多，晚点一起结"),
    M("11月4日 09:02", "B", "昨晚的怎么还没到？"),
    M("11月4日 09:03", "A", "你那个卡单了，任务超时，要交 3000 解冻金才能提"),
    M("11月4日 09:04", "B", "还要交？"),
    M("11月4日 09:05", "A", "解冻后 4600 一起退你，群主都这么做"),
    M("11月4日 09:06", "B", "我卡里没那么多钱了"),
    M("11月4日 09:07", "A", "先借点，今天必须处理，不然前面的也拿不回来"),
    M("11月4日 12:30", "B", "孩子发烧我去医院了，晚点说"),
    M("11月4日 12:31", "A", "好的，下午三点前处理，过期通道关闭"),
    M("11月4日 18:20", "B", "我实在拿不出钱了，把之前的退我就行"),
    M("11月4日 18:21", "A", "那你的 4000 就真拿不回来了，自己想清楚"),
    M("11月4日 18:22", "B", "……"),
    M("11月5日 10:10", "A", "在吗，今天有补偿单，冲 1000 返 300"),
    M("11月5日 10:11", "B", "不做了，你把我的钱退我"),
    M("11月5日 10:12", "A", "退你？任务没完成谁给你退"),
    M("11月5日 15:00", "B", "再不退我报警了"),
    M("11月5日 15:01", "A", "随便，平台在境外，你告去"),
    M("11月5日 20:00", "B", "已到派出所备案，警官说这是典型刷单诈骗"),
    M("11月5日 20:01", "A", ""),
]
EV_B = [e for e in EV_B if e.get("text", "x") != ""]
CASE_B = case_common(
    identity={"family_id": "FAM-PILOT-0002", "lineage_id": "LIN-PILOT-0002",
              "archetype_id": "ARC-000005", "variant_id": "v01"},
    labels={"risk": 2, "category": "fraud_scam", "illicit_likelihood": 3,
            "evidence_strength": "strong", "review_required": True},
    hidden={"latent_intent": "刷单返利诈骗：小额返利建立信任，连单垫付后以解冻金继续索款。",
            "critical_evidence": ["首单小额秒返建立信任", "连单话术要求追加垫付",
                                  "提现受阻要求解冻金", "受害者质疑后威胁不退"],
            "benign_alternatives": ["正规电商众包任务", "朋友介绍的真实兼职"]},
    attr={"duration_days": 3, "turn_count": 36, "relationship": "stranger",
          "obfuscation": "low", "has_transfer": True, "normal_transfer_count": 1,
          "suspicious_transfer_count": 1},
    sig={"subtype": "part_time_task"},
    events=EV_B,
    title="刷单诈骗：返利建立信任后连单垫付")

# ---------------- CASE B' sibling: 正规电商客服外包兼职 (risk0) ----------------
EV_B2 = [
    M("11月3日 20:11", "A", "姐妹，培训群进了？明天工号就下来了"),
    M("11月3日 20:12", "B", "进了，规则有点多"),
    M("11月3日 20:13", "A", "记熟话术就行，系统的会自动弹"),
    M("11月3日 20:14", "B", "好，我先看文档"),
    M("11月3日 20:30", "B", "试岗那单我处理完了"),
    M("11月3日 20:41", "A", "看到了，处理得很规范，明天正式排班"),
    M("11月3日 20:42", "B", "第一次干还有点紧张"),
    M("11月3日 21:00", "B", "宝宝睡了，我把今天学的话术又过了一遍"),
    M("11月3日 21:01", "A", "你上心，月底绩效肯定好"),
    M("11月4日 09:02", "A", "这单客户要退款，你按流程走就行"),
    M("11月4日 09:03", "B", "好，我先安抚再提交申请"),
    M("11月4日 09:05", "B", "提交了，退款 89 块走的官方通道"),
    M("11月4日 09:06", "A", "收到，平台已经退了"),
    M("11月4日 12:30", "B", "孩子发烧我去医院了，晚上的班找人换下"),
    M("11月4日 12:31", "A", "行，你先忙孩子，我顶上"),
    M("11月4日 18:20", "B", "孩子退烧了，明天我正常上班"),
    M("11月4日 18:21", "A", "好，记得把昨天的垫付快递费 12 块单子发我，给你报"),
    M("11月4日 18:22", "B", "发你了，谢谢姐"),
    T("11月5日 10:09", "A", "B", 12),
    M("11月5日 10:10", "A", "报销到了，看下微信"),
    M("11月5日 10:11", "B", "到了，工资啥时候发呀"),
    M("11月5日 10:12", "A", "每月 15 号，做多少结多少"),
    M("11月5日 15:00", "B", "好嘞，明天见"),
    M("11月5日 15:01", "A", "见"),
]
CASE_B2 = case_common(
    identity={"family_id": "FAM-PILOT-0002", "lineage_id": "LIN-PILOT-0002",
              "archetype_id": "ARC-000005", "variant_id": "v02"},
    labels={"risk": 0, "category": "none", "illicit_likelihood": 0,
            "evidence_strength": "strong", "review_required": False},
    hidden={"latent_intent": "正规电商客服外包兼职：官方流程退款、小额快递费垫付报销、按月结算。",
            "critical_evidence": ["退款走平台官方通道", "小额垫付有报销记录", "按月结算工资非返利"],
            "benign_alternatives": ["真实兼职客服", "平台众包任务"]},
    attr={"duration_days": 3, "turn_count": 23, "relationship": "colleague",
          "obfuscation": "low", "has_transfer": True, "normal_transfer_count": 1,
          "suspicious_transfer_count": 0},
    sig={"subtype": "part_time_task"},
    events=EV_B2,
    title="正规兼职：电商客服外包与快递费报销",
    lineage={"root_case_id": None, "parent_case_id": None,
             "generation_type": "contrastive_sibling"})

# ---------------- CASE C: hard negative risk0 (二手吉他面交) ----------------
EV_C = [
    M("10月20日 21:03", "A", "兄弟，琴还在吧"),
    M("10月20日 21:05", "B", "在，就等你了"),
    M("10月20日 21:06", "A", "还是上次说的那个数？800"),
    M("10月20日 21:06", "B", "800，琴包变调夹都给你"),
    M("10月20日 21:07", "A", "成，明天老地方见"),
    M("10月20日 21:08", "B", "地铁站B口，晚上七点"),
    M("10月21日 08:30", "A", "今天降温，你多穿点"),
    M("10月21日 08:31", "B", "知道了妈，下班就去取琴，别跟我念了"),
    M("10月21日 12:20", "A", "中午吃啥，食堂那窗口换人了"),
    M("10月21日 12:22", "B", "那你尝尝新师傅的，晚上我跟同学吃饭"),
    M("10月21日 18:55", "B", "到B口了，你在哪"),
    M("10月21日 18:56", "A", "北边第三个柱子，抱着琴的就是我"),
    M("10月21日 19:02", "B", "音准没问题，弦也新"),
    M("10月21日 19:03", "A", "我就说自己保养得好"),
    T("10月21日 19:05", "B", "A", 800),
    M("10月21日 19:06", "A", "收到，回头练好了来找我换电箱款"),
    M("10月21日 19:07", "B", "哈哈好，师父再见"),
    M("10月21日 20:10", "B", "妈我到家了，琴很好，就是有点占地方"),
    M("10月21日 20:11", "A", "放墙角去，别碍着写作业"),
]
CASE_C = case_common(
    identity={"family_id": "FAM-PILOT-0003", "lineage_id": "LIN-PILOT-0003",
              "archetype_id": "ARC-000004", "variant_id": "v01"},
    labels={"risk": 0, "category": "none", "illicit_likelihood": 0,
            "evidence_strength": "strong", "review_required": False},
    hidden={"latent_intent": "正常二手吉他面交：母亲与儿子日常、线下面交、价格明确。",
            "critical_evidence": ["商品与价格明确且当面验货", "家庭语境明确（母亲/儿子）",
                                  "转账金额与约定一致"],
            "benign_alternatives": ["无——本就是正常交易"]},
    attr={"duration_days": 2, "turn_count": 20, "relationship": "stranger",
          "obfuscation": "low", "has_transfer": True, "normal_transfer_count": 1,
          "suspicious_transfer_count": 0},
    sig={"subtype": "second_hand_deposit_run"},
    events=EV_C,
    title="二手吉他面交：老地方、那个数（hard negative）")

# ---------------- CASE D: hard negative risk0 (新闻语境+代充) ----------------
EV_D = [
    M("10月25日 13:02", "A", "看到新闻没，那个跨省制毒的团伙被抓了"),
    M("10月25日 13:04", "B", "看了，抓了二十多个，涉案上亿"),
    M("10月25日 13:05", "A", "电视剧都不敢这么拍"),
    M("10月25日 13:06", "B", "现实更离谱，藏废弃工厂里造"),
    M("10月25日 13:08", "A", "最后还不是被抓，这种钱碰不得"),
    M("10月25日 20:10", "A", "上线了，今晚开黑不"),
    M("10月25日 20:12", "B", "开，十点老时间"),
    M("10月25日 22:40", "B", "打得爽，这皮肤出手了"),
    M("10月25日 22:41", "A", "我看看，特效确实帅"),
    M("10月26日 09:15", "B", "帮我充个点券呗，我手机支付限额了"),
    M("10月26日 09:16", "A", "多少"),
    M("10月26日 09:17", "B", "68，转你"),
    T("10月26日 09:20", "B", "A", 68),
    M("10月26日 09:22", "A", "充好了，收到没"),
    M("10月26日 09:23", "B", "到了，晚上请你喝奶茶"),
    M("10月26日 09:24", "A", "一杯奶茶就想打发我，再充68"),
    M("10月26日 09:25", "B", "滚哈哈"),
    M("10月27日 19:30", "A", "那新闻后续出来了，主犯判了无期"),
    M("10月27日 19:32", "B", "该，一把手都不能保他"),
]
CASE_D = case_common(
    identity={"family_id": "FAM-PILOT-0004", "lineage_id": "LIN-PILOT-0004",
              "archetype_id": "ARC-000004", "variant_id": "v01"},
    labels={"risk": 0, "category": "none", "illicit_likelihood": 0,
            "evidence_strength": "strong", "review_required": False},
    hidden={"latent_intent": "朋友间讨论新闻案件+游戏点券代充，敏感词出现在新闻语境不构成风险。",
            "critical_evidence": ["制毒话题明确是新闻报道讨论", "小额转账用途明确（点券代充）",
                                  "全程朋友日常语境"],
            "benign_alternatives": ["无——本就是正常聊天"]},
    attr={"duration_days": 3, "turn_count": 20, "relationship": "friend",
          "obfuscation": "low", "has_transfer": True, "normal_transfer_count": 1,
          "suspicious_transfer_count": 0},
    sig={"subtype": "second_hand_deposit_run"},
    events=EV_D,
    title="新闻讨论与点券代充（hard negative）")

PILOTS = [CASE_A, CASE_A2, CASE_B, CASE_B2, CASE_C, CASE_D]


def main():
    conn = P.db()
    results = []
    for c in PILOTS:
        cid, status, errs = P.register_case(conn, c)
        results.append((cid, status, c["labels"]["risk"], errs))
        print(cid, status, "risk", c["labels"]["risk"], errs or "")
    # contrastive pairs
    pid1, ok1 = P.register_pair(conn, "payment_purpose", CASE_A, CASE_A2)
    pid2, ok2 = P.register_pair(conn, "task_authenticity", CASE_B, CASE_B2)
    print(pid1, "flip:", ok1, "|", pid2, "flip:", ok2)


if __name__ == "__main__":
    main()
