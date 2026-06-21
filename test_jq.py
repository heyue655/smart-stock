# -*- coding: utf-8 -*-

# 月度/单日回测版本（申万三级行业版）：输入月份或具体日期，选股 + 次日卖出，汇总盈亏
# 行业过滤：sw_l3 为主 + sw_l2 兜底；活跃度：大盘涨时相对(>大盘涨幅)，大盘跌时绝对(>底线)

from __future__ import division
from jqdata import *
# 注意：jqdata 会把 datetime 覆盖为 module，必须放在 jqdata 之后再导入
import datetime as _dt
from datetime import timedelta
import pandas as pd
datetime = _dt.datetime

# ============================================================
# 【可调参数】—— 只需修改这里
# ============================================================
TARGET_DATE       = '2026-06'      # 回测月份（YYYY-MM）或具体日期（YYYY-MM-DD），日期则仅回测该日

SCREEN_START_TIME = '09:30:00'     # 分钟线起始时间
SCREEN_END_TIME   = '14:57:00'     # 尾盘截止时间（选股时间点）

HIST_DAYS_COUNT   = 6              # 拉取日线天数（含T日）
SMART_RISE_LOOKBACK = 30           # 智能过滤累计涨幅回看天数（交易日），用于判断前期是否已大涨

PCT_CHG_MIN       = 6.0            # 涨幅下限（%）
PCT_CHG_MAX       = 9.0              # 涨幅上限（%）
MKT_CAP_MIN       = 50.0           # 流通市值下限（亿元）
MKT_CAP_MAX       = 300.0          # 流通市值上限（亿元）

VOL_RATIO_MIN     = 1.8            # 量比下限
VOL_RATIO_MAX     = 5.5            # 量比上限
UPPER_SHADOW_MAX  = 2              # 上影线最大比例（%，收紧至2，全量回测验证优于3）
TURNOVER_MIN      = 5              # 换手率下限（%）
TURNOVER_MAX      = 12             # 换手率上限（%）
VWAP_ABOVE_MIN    = 0.8            # VWAP上方时间占比下限（0~1），低于此值过滤
VWAP_ABOVE_MAX    = 1              # VWAP上方时间占比上限（0~1），高于此值过滤

TOP_N             = 3              # 每日最终选股数量
FALLBACK_RANGE    = [0, 2]         # 精筛无标的时回退区间（0-indexed，闭区间）：从候选按成交额排序后取第[start, end]只，如[2,3]=取第3~4只
FALLBACK_POSITION_RATIO = 0.5      # 回退选股时的仓位比例（0~1），如0.5表示半仓
DAILY_CAPITAL     = 100000.0       # 每日本金（均分给当日选中的每只股）
SELL_TIME         = '10:45:00'     # 次日卖出时间
STOP_LOSS_PCT      = -10.0           # 止损线（%）：次日10点前分钟线跌破此比例立即卖出
DELAY_SELL_DAYS    = 3               # 延迟卖出天数：0=T+1卖出；>0=若T+1亏损则持有，每日检查回本，第N日强制卖出

# --- 顶部风险过滤 ---
FILTER_TOP_RISK         = False  # True=过滤有顶部风险的标的；False=跳过风险检查
FILTER_TOP_RISK_SINGLE  = False  # True=单只选股日也执行顶部风险过滤；False=仅1只时只提示
WARN_DEVIATION_MA20     = 15.0   # MA20乖离率超过此值视为风险（%）
WARN_DEVIATION_MA60     = 25.0   # MA60乖离率超过此值视为风险（%）
WARN_OVERHEAT_VOL       = 3.5    # 量比>=此值且换手率>=过热换手率则视为过热
WARN_OVERHEAT_TURN      = 10.0   # 过热换手率阈值（%）
WARN_GAP_OPEN_PCT       = 3.0    # 跳空高开幅度阈值（%）：开盘价/昨收-1>=此值视为跳空
WARN_GAP_FLAT_RANGE     = 2.0    # 跳空后日内波动<(最高-最低)/开盘价<此值视为"横盘出货"（%）
WARN_SECTOR_RANK_PCT    = 0.5    # 板块内涨幅排名后50%%视为跟风股（0=领涨，1=垫底）

# --- 全局额外风险提示 ---
GLOBAL_RISK_WARN = True           # True=触发条件时过滤掉该标的；False=仅打印提醒不过滤
RISK_SECTORS     = ['建筑', '医疗', '医院', '超市', '消费', '地产', '诊断', '塑料', '种植', '生物', '休闲', '农林牧', 
                                   '传媒', '影视', '美容']  # 回溯中高风险行业关键字
RISK_MONTHS      = ['01']         # 回溯中高风险月份
RISK_STOCKS      = ['天津普林', '002134']  # 回溯中高风险个股（名称或代码）

# --- 大盘 / ST / 行业 过滤 ---
SH_DROP_LIMIT     = -2.0           # 上证跌幅阈值（%）：<=此值不选股
FILTER_ST         = True           # 过滤 ST / 退市
SECTOR_EXCLUDE_INACTIVE = True      # 排除当日不活跃行业
SECTOR_RELATIVE_MODE  = True        # True=活跃度相对大盘判定；False=沿用绝对阈值
SECTOR_RELATIVE_MULT  = 0.5         # 大盘涨时：板块涨幅需 > 大盘涨幅×系数 才算活跃
SECTOR_ABSOLUTE_FLOOR = 0.0         # 大盘跌/平时：板块涨幅需 > 此绝对值（%）才算活跃
SECTOR_L2_DISPLAY     = True        # 选股结果是否同时显示二级行业参考
SELECT_FROM_ACTIVE_SECTORS = False   # True=必须从当日涨幅前N的一级行业中选股；无候选时回退到所有一级行业
SELECT_ACTIVE_TOP_N       = 3       # 配合上面开关，取涨幅前N的一级行业

# --- 趋势过滤（排除超跌反弹）---
TREND_ABOVE_MA5   = True           # T日收盘价必须 >= MA5（5日均线）
TREND_PREV_RET_MIN = -3.0          # 过去N天(不含T日)累计涨跌幅下限(%)：<=此值视为前期超跌，剔除
FILTER_PREV_DAY_DOWN = False        # True=T-1日股价下跌则放弃该股；False=不过滤
PREV_DAY_DOWN_THRESHOLD = 0.2      # T-1日涨幅阈值(%)，低于此值视为下跌
FILTER_PREV_DAY_UPPER_SHADOW = False  # True=T-1日上影线超过阈值则过滤；False=不过滤
PREV_DAY_UPPER_SHADOW_MAX = 5.0    # T-1日上影线阈值(%)

# --- 均线多头排列过滤 ---
FILTER_MA_TREND   = True           # True=要求均线多头排列且向上；False=不过滤
MA_TREND_PERIODS  = [5, 10, 20, 30]  # 均线周期列表
MA_TREND_LOOKBACK = 31             # 计算MA所需回看天数（最大周期+1，用于算前一日MA）
MA_UP_CHECK_DAYS  = 3              # 检查最近N日MA是否连续向上

# --- 成交量过滤 ---
FILTER_VOLUME_DOUBLE = True       # True=T日成交量较前一日超过阈值则过滤；False=不过滤
VOLUME_DOUBLE_THRESHOLD = 1.65     # 成交量翻倍阈值（T日或T-1日任意一天量>=前日量*阈值则过滤）
VOLUME_DOUBLE_CHECK_PREV = False    # True=同时检查T-1/T-2成交量；False=只检查T/T-1成交量
VOLUME_FILTER_SMART = False        # 智能过滤开关：True=前期涨幅小(<阈值)的放量股保留；False=直接过滤
VOLUME_FILTER_RISE_THRESHOLD = 12.0  # 智能过滤前期涨幅阈值(%)：仅当VOLUME_FILTER_SMART=True时生效

# --- 量价背离过滤 ---
FILTER_VOLUME_DIVERGENCE = True   # True=近5日涨但量能萎缩则过滤；False=不过滤
VOLUME_DIVERGENCE_DAYS = 5         # 量价背离检查天数

# --- 情绪比值过滤（成交额万亿 / (上涨数/总股票数)，总股票数含ST/退市）---
SENTIMENT_RATIO_FILTER    = False   # True=按比值过滤选股；False=不过滤仅给风险提示
SENTIMENT_MONEY_THRESHOLD = 2.1    # 总成交额阈值（万亿）
SENTIMENT_RATIO_LOW_MKT   = 3.8    # 总成交额 < 阈值 时要求的最低比值
SENTIMENT_RATIO_HIGH_MKT  = 2.0    # 总成交额 >= 阈值 时要求的最低比值

VERBOSE_DAILY     = False          # 是否打印每日漏斗详情（True=详细, False=仅汇总）

# --- CSV 导出 ---
EXPORT_CSV        = False           # 是否导出 CSV（聚宽研究环境左侧文件树可下载）
CSV_DIR           = ''             # 导出目录，空=当前目录；研究环境建议留空
# ============================================================

# --- 自动计算 ---
_fmt = '%H:%M:%S'
SCREEN_MINUTES = float(int(
    (datetime.strptime(SCREEN_END_TIME, _fmt) - datetime.strptime(SCREEN_START_TIME, _fmt)
    ).total_seconds() / 60
))
TRADING_MINUTES = 240.0


def _dw(s):
    """计算字符串显示宽度（CJK字符占2列）"""
    w = 0
    for c in str(s):
        w += 2 if '\u4e00' <= c <= '\u9fff' or '\u3000' <= c <= '\u303f' else 1
    return w


def _pad(s, width):
    """按显示宽度右补空格"""
    return str(s) + ' ' * max(0, width - _dw(s))


def _check_global_risks(details, t_date):
    """检查选股是否触发全局风险条件（行业/月份/个股），打印提醒"""
    if not GLOBAL_RISK_WARN or not details:
        return
    _warnings = []
    _m = t_date[5:7]
    if _m in RISK_MONTHS:
        _warnings.append("⚡ 当前为历史高风险月份(%s月)，全量回测显示该月胜率偏低" % _m)
    for _d in details:
        _sector = _d.get('sector', '')
        _sector_l1 = _d.get('sector_l1', '')
        _sector_l2 = _d.get('sector_l2', '')
        _name = _d.get('name', '')
        _code = _d.get('code', '')
        for _kw in RISK_SECTORS:
            if _kw in _sector or _kw in _sector_l1 or _kw in _sector_l2 or _kw in _name:
                _warnings.append("⚡ %s(%s) 属于回溯中高风险行业(%s)" % (_name, _code, _sector_l1))
                break
        for _kw in RISK_STOCKS:
            if _kw in _name or _kw in _code:
                _warnings.append("⚡ %s(%s) 属于回溯中高风险个股" % (_name, _code))
                break
    if _warnings:
        print("    [全局风险] 回溯数据警示：历史回测中该类标的盈亏表现较差，请谨慎判断")
        for _w in _warnings:
            print("      " + _w)


# ============================================================
# 核心函数：单日选股 + 次日卖出
# ============================================================
def _log(msg):
    if VERBOSE_DAILY:
        print(msg)


def screen_one_day(target_date, sell_days, stocks_info_cache=None):
    """
    对 target_date 选股，在 sell_days 列表中按延迟卖出逻辑卖出。
    sell_days: [T+1, T+2, ..., T+N] 交易日列表
    返回: dict(date, picks_count, total_buy, total_sell, total_pnl, pnl_pct, details)
          details 是 list of dict 每只股票的盈亏明细
    若当日无选股或大盘情绪差，picks_count=0，其它为 0
    """
    result = {
        'date': target_date,
        'next_day': sell_days[0] if sell_days else '',
        'picks_count': 0,
        'total_buy': 0.0,
        'total_sell': 0.0,
        'total_pnl': 0.0,
        'pnl_pct': 0.0,
        'details': [],
        'skipped_reason': '',
    }

    # --- 大盘情绪门控 ---
    try:
        _sh_df = get_price('000001.XSHG', count=1, end_date=target_date, frequency='daily',
                           fields=['close', 'pre_close'])
    except Exception as e:
        result['skipped_reason'] = 'get_price(SH) error: %s' % str(e)
        return result

    if _sh_df is None or len(_sh_df) == 0:
        result['skipped_reason'] = '无上证数据'
        return result

    _sh_chg = (float(_sh_df['close'].iloc[0]) - float(_sh_df['pre_close'].iloc[0])) \
              / float(_sh_df['pre_close'].iloc[0]) * 100
    result['sh_change'] = round(_sh_chg, 2)
    result['sh_index'] = round(float(_sh_df['close'].iloc[0]), 2)
    if _sh_chg <= SH_DROP_LIMIT:
        result['skipped_reason'] = '大盘跌%.2f%% <= %.2f%%' % (_sh_chg, SH_DROP_LIMIT)
        return result

    # --- 股票池 (全量用于大盘情绪统计；FILTER_ST 仅用于候选筛选) ---
    stocks_info = stocks_info_cache if stocks_info_cache is not None else get_all_securities(['stock'])
    all_stock_list = stocks_info.index.tolist()
    total_stock_count = len(all_stock_list)
    if FILTER_ST:
        _mask_st = ~stocks_info['display_name'].str.contains(u'ST|退', na=False)
        st_excluded = set(stocks_info[~_mask_st].index.tolist())
    else:
        st_excluded = set()

    # --- 日线数据（全量，含ST，便于统计真实大盘情绪）---
    try:
        df_daily = get_price(all_stock_list, count=HIST_DAYS_COUNT, end_date=target_date, frequency='daily',
                             fields=['close', 'pre_close', 'high', 'low', 'volume', 'money'], panel=False)
    except Exception as e:
        result['skipped_reason'] = 'get_price(daily) error: %s' % str(e)
        return result
    if df_daily is None or len(df_daily) == 0:
        result['skipped_reason'] = '无日线数据'
        return result

    df_flat = df_daily.reset_index()
    if 'index' in df_flat.columns:
        df_flat.drop('index', axis=1, inplace=True)
    df_flat = df_flat.loc[:, ~df_flat.columns.duplicated()]

    all_days = sorted(df_flat['time'].unique())
    hist_days = all_days[:-1]
    t_day = all_days[-1]
    df_hist = df_flat[df_flat['time'].isin(hist_days)]
    avg_vol_5d = df_hist.groupby('code')['volume'].sum() / (len(hist_days) * TRADING_MINUTES)

    # 趋势指标：MA5（含T日）+ 过去N天累计涨跌幅（T-1 vs T-N，不含T日）
    ma5_series = df_flat.groupby('code')['close'].mean()
    if len(hist_days) >= 2:
        _prev_last  = df_hist.groupby('code')['close'].last()    # T-1
        _prev_first = df_hist.groupby('code')['close'].first()   # T-N
        _prev_ret   = (_prev_last - _prev_first) / _prev_first * 100
    else:
        _prev_ret = None

    # T-1日涨跌幅
    _prev_day_pct = None
    _prev_day_upper_shadow = None
    if len(hist_days) >= 2:
        _t1_day = hist_days[-1]
        _t2_day = hist_days[-2]
        _t1_data = df_flat[df_flat['time'] == _t1_day].set_index('code')
        _t1_close = _t1_data['close']
        _t2_close = df_flat[df_flat['time'] == _t2_day].set_index('code')['close']
        _prev_day_pct = (_t1_close - _t2_close) / _t2_close * 100
        _prev_day_upper_shadow = (_t1_data['high'] - _t1_close) / _t1_close * 100

    # --- 均线多头排列过滤：拉取更长历史数据计算 MA10/20/30 ---
    _ma_data = {}
    if FILTER_MA_TREND:
        try:
            _ma_hist = get_price(all_stock_list, count=MA_TREND_LOOKBACK, end_date=target_date,
                                 frequency='daily', fields=['close'], panel=False)
            _ma_hist = _ma_hist.reset_index()
            if 'index' in _ma_hist.columns:
                _ma_hist.drop('index', axis=1, inplace=True)
            _ma_hist = _ma_hist.loc[:, ~_ma_hist.columns.duplicated()]
            _ma_days = sorted(_ma_hist['time'].unique())
            
            for _period in MA_TREND_PERIODS:
                if len(_ma_days) >= _period:
                    _recent = _ma_hist[_ma_hist['time'].isin(_ma_days[-_period:])]
                    _ma_data[_period] = _recent.groupby('code')['close'].mean()
                    if len(_ma_days) >= _period + 1:
                        _prev_recent = _ma_hist[_ma_hist['time'].isin(_ma_days[-(_period+1):-1])]
                        _ma_data['prev_%d' % _period] = _prev_recent.groupby('code')['close'].mean()
        except Exception as _e:
            print("    [W] MA趋势过滤数据拉取异常: %s，跳过此过滤" % str(_e)[:50])
            _ma_data = {}

    t_day_basic = df_flat[df_flat['time'] == t_day].copy().set_index('code')
    t_day_basic['pct_chg'] = (t_day_basic['close'] - t_day_basic['pre_close']) / t_day_basic['pre_close'] * 100
    t_day_basic['avg_vol_5d'] = avg_vol_5d
    t_day_basic['ma5'] = ma5_series
    if _prev_ret is not None:
        t_day_basic['prev_ret_pct'] = _prev_ret
    else:
        t_day_basic['prev_ret_pct'] = 0.0
    if _prev_day_pct is not None:
        t_day_basic['prev_day_pct'] = _prev_day_pct
    else:
        t_day_basic['prev_day_pct'] = 0.0
    if _prev_day_upper_shadow is not None:
        t_day_basic['prev_day_upper_shadow'] = _prev_day_upper_shadow
    else:
        t_day_basic['prev_day_upper_shadow'] = 0.0

    # 大盘统计（基于全量股票：含ST/退市，与用户定义一致）
    result['sh_rise_count'] = int((t_day_basic['pct_chg'] > 0).sum())
    result['sh_fall_count'] = int((t_day_basic['pct_chg'] < 0).sum())
    result['sh_total_money'] = round(float(t_day_basic['money'].sum()), 0)
    result['sh_total_volume'] = round(float(t_day_basic['volume'].sum()), 0)
    result['sh_total_stock'] = total_stock_count

    # --- 情绪比值：成交额(万亿) / (上涨数/总股票数) ---
    _money_wy = result['sh_total_money'] / 1e12   # 万亿
    _rise_ratio_stock = (result['sh_rise_count'] / total_stock_count) if total_stock_count > 0 else 0.0
    if _rise_ratio_stock > 0:
        _sent_ratio = _money_wy / _rise_ratio_stock
    else:
        _sent_ratio = 0.0
    result['sentiment_ratio'] = round(_sent_ratio, 3)
    # 阈值判定
    _need_ratio = SENTIMENT_RATIO_LOW_MKT if _money_wy < SENTIMENT_MONEY_THRESHOLD else SENTIMENT_RATIO_HIGH_MKT
    result['sentiment_need'] = _need_ratio
    _sent_pass = _sent_ratio >= _need_ratio
    result['sentiment_pass'] = _sent_pass
    if not _sent_pass:
        _warn = u'情绪比值 %.2f < 需求 %.2f (成交额%.2f万亿,上涨%d/%d)' % (
            _sent_ratio, _need_ratio, _money_wy,
            result['sh_rise_count'], total_stock_count)
        result['sentiment_warning'] = _warn
        if SENTIMENT_RATIO_FILTER:
            result['skipped_reason'] = _warn
            return result
    else:
        result['sentiment_warning'] = ''

    # --- 市值 ---
    q = query(valuation.code, valuation.circulating_market_cap, valuation.circulating_cap).filter(
        valuation.code.in_(all_stock_list))
    cap_df = get_fundamentals(q, date=target_date).set_index('code')
    pre_picks = t_day_basic.join(cap_df, how='inner')
    # 应用 ST 过滤（仅影响候选池，不影响上面已算好的大盘情绪）
    if st_excluded:
        pre_picks = pre_picks[~pre_picks.index.isin(st_excluded)]
    if len(pre_picks) == 0:
        result['skipped_reason'] = '无基本面数据'
        return result

    # --- 行业活跃度（主分类：申万三级(sw_l3)；兜底：申万二级(sw_l2)）---
    _active_sectors = None
    _l1_chg = None
    _l1_fallback = False
    sector_map = {}        # {code: sw_l3_name 或 sw_l2_name(兜底)}
    sector_l2_map = {}     # {code: sw_l2_name} 供展示参考
    sector_l1_map = {}     # {code: sw_l1_name} 供展示参考
    if SECTOR_EXCLUDE_INACTIVE or SELECT_FROM_ACTIVE_SECTORS:
        _all_codes = pre_picks.index.tolist()
        try:
            _ind = get_industry(_all_codes, date=target_date)
            for _c, _info in _ind.items():
                if not _info:
                    continue
                _sw1 = _info.get('sw_l1', {}) or {}
                _sw3 = _info.get('sw_l3', {}) or {}
                _sw2 = _info.get('sw_l2', {}) or {}
                _sw1_name = _sw1.get('industry_name', '')
                _sw3_name = _sw3.get('industry_name', '')
                _sw2_name = _sw2.get('industry_name', '')
                sector_l2_map[_c] = _sw2_name
                sector_l1_map[_c] = _sw1_name
                if _sw3_name:
                    sector_map[_c] = _sw3_name
                elif _sw2_name:
                    sector_map[_c] = _sw2_name
        except Exception:
            pass
        pre_picks['sector'] = pre_picks.index.map(lambda c: sector_map.get(c, ''))
        pre_picks['sector_l2'] = pre_picks.index.map(lambda c: sector_l2_map.get(c, ''))
        _sector_chg = pre_picks[pre_picks['sector'] != ''].groupby('sector')['pct_chg'].mean()
        _sector_chg = _sector_chg.sort_values(ascending=False)

        # L2 行业涨跌（供展示用）
        _l2_chg = pre_picks[pre_picks['sector_l2'] != ''] \
            .groupby('sector_l2')['pct_chg'].mean().sort_values(ascending=False)
        result['sector_chg_l3'] = {name: round(val, 2) for name, val in _sector_chg.items()}
        result['sector_chg_l2'] = {name: round(val, 2) for name, val in _l2_chg.items()}

        # L1 行业涨跌（供展示用）
        pre_picks['sector_l1'] = pre_picks.index.map(lambda c: sector_l1_map.get(c, ''))
        _l1_chg = pre_picks[pre_picks['sector_l1'] != ''] \
            .groupby('sector_l1')['pct_chg'].mean().sort_values(ascending=False)
        result['top_l1_sectors'] = [(name, round(val, 2)) for name, val
                                     in _l1_chg.head(10).items()]
        result['sector_chg_l1'] = {name: round(val, 2) for name, val in _l1_chg.items()}
        # 活跃度阈值：大盘涨时相对(>大盘涨幅)，大盘跌/平时绝对(>底线)
        if SECTOR_RELATIVE_MODE and _sh_chg > 0:
            _sector_thr = _sh_chg * SECTOR_RELATIVE_MULT
        else:
            _sector_thr = SECTOR_ABSOLUTE_FLOOR
        _active_sectors = set(_sector_chg[_sector_chg > _sector_thr].index.tolist())
    else:
        pre_picks['sector'] = ''

    # --- 初筛基础条件 ---
    mask_basic = (
        (pre_picks['pct_chg'] >= PCT_CHG_MIN) & (pre_picks['pct_chg'] <= PCT_CHG_MAX) &
        (pre_picks['circulating_market_cap'] >= MKT_CAP_MIN) &
        (pre_picks['circulating_market_cap'] <= MKT_CAP_MAX)
    )
    if TREND_ABOVE_MA5:
        mask_basic = mask_basic & (pre_picks['close'] >= pre_picks['ma5'])
    if TREND_PREV_RET_MIN is not None:
        mask_basic = mask_basic & (pre_picks['prev_ret_pct'] >= TREND_PREV_RET_MIN)
    if FILTER_PREV_DAY_DOWN:
        mask_basic = mask_basic & (pre_picks['prev_day_pct'] >= PREV_DAY_DOWN_THRESHOLD)
    if FILTER_PREV_DAY_UPPER_SHADOW:
        mask_basic = mask_basic & (pre_picks['prev_day_upper_shadow'] <= PREV_DAY_UPPER_SHADOW_MAX)

    # --- 均线多头排列 + 向上趋势过滤 ---
    if FILTER_MA_TREND and _ma_data:
        _sorted_periods = sorted(MA_TREND_PERIODS)
        _ma_mask = pd.Series(True, index=pre_picks.index)
        
        for i in range(len(_sorted_periods) - 1):
            _short = _sorted_periods[i]
            _long = _sorted_periods[i + 1]
            if _short in _ma_data and _long in _ma_data:
                _ma_mask = _ma_mask & (_ma_data[_short].reindex(pre_picks.index) > _ma_data[_long].reindex(pre_picks.index))
        
        for _period in _sorted_periods:
            _cur_key = _period
            _prev_key = 'prev_%d' % _period
            if _cur_key in _ma_data and _prev_key in _ma_data:
                _cur_ma = _ma_data[_cur_key].reindex(pre_picks.index)
                _prev_ma = _ma_data[_prev_key].reindex(pre_picks.index)
                _ma_mask = _ma_mask & (_cur_ma > _prev_ma)
        
        mask_basic = mask_basic & _ma_mask.fillna(False)

    # --- 活跃行业选股（Top N 一级行业）---
    candidate_list = []
    if SELECT_FROM_ACTIVE_SECTORS:
        _l1_sorted = _l1_chg.index.tolist()
        _topN_l1 = set(_l1_sorted[:SELECT_ACTIVE_TOP_N])
        result['topN_l1_sectors'] = list(_topN_l1)
        _topN_mask = pre_picks['sector_l1'].map(lambda s: s in _topN_l1)
        candidate_list = pre_picks[mask_basic & _topN_mask].index.tolist()
        if not candidate_list:
            _all_l1_mask = pre_picks['sector_l1'].map(lambda s: s != '')
            candidate_list = pre_picks[mask_basic & _all_l1_mask].index.tolist()
            if candidate_list:
                _l1_fallback = True
                result['skipped_reason'] = 'Top%d一级行业无候选->回退到所有一级行业' % SELECT_ACTIVE_TOP_N
        if not candidate_list:
            result['skipped_reason'] = '活跃行业(Top%d一级)无候选' % SELECT_ACTIVE_TOP_N
            return result

    # --- 成交量翻倍过滤 ---
    if FILTER_VOLUME_DOUBLE and len(hist_days) >= 1:
        # 获取前一日的成交量
        _prev_day = hist_days[-1]
        _prev_vol = df_flat[df_flat['time'] == _prev_day].groupby('code')['volume'].sum()
        # T日成交量
        _t_vol = t_day_basic['volume']
        # 计算T日翻倍比例（对齐到 mask_basic 的索引）
        _vol_ratio = _t_vol.reindex(mask_basic.index) / _prev_vol.reindex(mask_basic.index)
        
        # 计算T-1日翻倍比例（需要T-2日数据）
        _vol_ratio_prev = None
        if VOLUME_DOUBLE_CHECK_PREV and len(hist_days) >= 2:
            _prev2_day = hist_days[-2]
            _prev2_vol = df_flat[df_flat['time'] == _prev2_day].groupby('code')['volume'].sum()
            _vol_ratio_prev = _prev_vol.reindex(mask_basic.index) / _prev2_vol.reindex(mask_basic.index)
        
        if VOLUME_FILTER_SMART:
            # 智能过滤：放量超阈值但前期涨幅小的保留（可能是启动）
            # 单独拉取更长时间的数据来计算累计涨幅
            try:
                _long_hist = get_price(mask_basic.index.tolist(), count=SMART_RISE_LOOKBACK, end_date=target_date,
                                       frequency='daily', fields=['close'], panel=False)
                _long_hist = _long_hist.reset_index()
                if 'index' in _long_hist.columns:
                    _long_hist.drop('index', axis=1, inplace=True)
                _long_hist = _long_hist.loc[:, ~_long_hist.columns.duplicated()]
                # 排除T日，只算到T-1
                _long_hist = _long_hist[_long_hist['time'] < target_date]
                _hist_min_close = _long_hist.groupby('code')['close'].min()
                _prev_close = _long_hist.groupby('code')['close'].last()  # T-1
                _cum_rise = (_prev_close - _hist_min_close) / _hist_min_close * 100
                _cum_rise = _cum_rise.reindex(mask_basic.index).fillna(0)
            except Exception as _e:
                print("    [W] 智能过滤拉取历史数据异常: %s，回退到5日窗口" % str(_e)[:50])
                _hist_min_close = df_hist.groupby('code')['close'].min()
                _prev_close = df_hist.groupby('code')['close'].last()
                _cum_rise = (_prev_close - _hist_min_close) / _hist_min_close * 100
                _cum_rise = _cum_rise.reindex(mask_basic.index).fillna(0)
            _vol_pass = _vol_ratio < VOLUME_DOUBLE_THRESHOLD
            if _vol_ratio_prev is not None:
                _vol_pass = _vol_pass & (_vol_ratio_prev < VOLUME_DOUBLE_THRESHOLD)
            _vol_mask = _vol_pass | (_cum_rise < VOLUME_FILTER_RISE_THRESHOLD)
        else:
            # 直接过滤放量超阈值的股票
            _vol_mask = _vol_ratio < VOLUME_DOUBLE_THRESHOLD
            if _vol_ratio_prev is not None:
                _vol_mask = _vol_mask & (_vol_ratio_prev < VOLUME_DOUBLE_THRESHOLD)
        mask_basic = mask_basic & _vol_mask.fillna(True)

    # --- 量价背离过滤 ---
    if FILTER_VOLUME_DIVERGENCE and len(hist_days) >= VOLUME_DIVERGENCE_DAYS:
        # 计算近N日涨幅和量能变化
        _recent_days = hist_days[-VOLUME_DIVERGENCE_DAYS:]
        _older_days = hist_days[:-VOLUME_DIVERGENCE_DAYS] if len(hist_days) > VOLUME_DIVERGENCE_DAYS else hist_days[:VOLUME_DIVERGENCE_DAYS]
        
        if len(_older_days) > 0:
            # 近N日收盘价
            _recent_close_first = df_flat[df_flat['time'] == _recent_days[0]].set_index('code')['close']
            _recent_close_last = df_flat[df_flat['time'] == _recent_days[-1]].set_index('code')['close']
            _recent_pct = (_recent_close_last - _recent_close_first) / _recent_close_first * 100
            
            # 近N日均量 vs 更早N日均量
            _recent_vol = df_flat[df_flat['time'].isin(_recent_days)].groupby('code')['volume'].mean()
            _older_vol = df_flat[df_flat['time'].isin(_older_days)].groupby('code')['volume'].mean()
            
            # 量价背离：涨但量缩
            _divergence_mask = ~((_recent_pct > 0) & (_recent_vol < _older_vol))
            mask_basic = mask_basic & _divergence_mask.reindex(mask_basic.index).fillna(True)

    # --- 初筛 ---
    if SELECT_FROM_ACTIVE_SECTORS:
        # 已在上面计算好 candidate_list
        if not candidate_list:
            result['skipped_reason'] = '初筛无候选'
            return result
    else:
        if _active_sectors is not None:
            mask_basic = mask_basic & pre_picks['sector'].map(lambda s: s in _active_sectors)
        candidate_list = pre_picks[mask_basic].index.tolist()
        if not candidate_list:
            result['skipped_reason'] = '初筛无候选'
            return result

    # --- 分钟线精算 ---
    end_time = target_date + ' ' + SCREEN_END_TIME
    try:
        df_min = get_price(candidate_list, start_date=target_date + ' ' + SCREEN_START_TIME,
                           end_date=end_time, frequency='1m', fields=['close', 'avg', 'high', 'low', 'open', 'volume', 'money'],
                           panel=False)
    except Exception as e:
        result['skipped_reason'] = '分钟线获取失败: %s' % str(e)[:50]
        return result
    if df_min is None or len(df_min) == 0:
        result['skipped_reason'] = '无分钟线数据'
        return result
    df_min_flat = df_min.reset_index()
    if 'index' in df_min_flat.columns:
        df_min_flat.drop('index', axis=1, inplace=True)
    df_min_flat = df_min_flat.loc[:, ~df_min_flat.columns.duplicated()]

    vol_intra = df_min_flat.groupby('code')['volume'].sum()
    _actual_minutes = float(len(df_min_flat['time'].drop_duplicates()))
    _screen_mins = _actual_minutes if _actual_minutes > 0 else SCREEN_MINUTES
    min_final = df_min_flat.groupby('code').last()
    min_final['vol_ratio'] = (vol_intra / _screen_mins) / pre_picks['avg_vol_5d']
    min_final['today_high'] = df_min_flat.groupby('code')['high'].max()
    min_final['upper_shadow'] = (min_final['today_high'] - min_final['close']) / min_final['close'] * 100

    df_min_flat = df_min_flat.sort_values(['code', 'time'])
    df_min_flat['cum_money'] = df_min_flat.groupby('code')['money'].cumsum()
    df_min_flat['cum_volume'] = df_min_flat.groupby('code')['volume'].cumsum()
    df_min_flat['vwap'] = df_min_flat['cum_money'] / df_min_flat['cum_volume']

    _valid = df_min_flat[df_min_flat['vwap'] > 0]
    _above_cnt = _valid[_valid['close'] >= _valid['vwap']].groupby('code').size()
    _total_cnt = _valid.groupby('code').size()
    vwap_above_ratio = (_above_cnt / _total_cnt).fillna(0)

    min_final['vwap'] = df_min_flat.groupby('code')['vwap'].last()
    if 'money' in min_final.columns:
        min_final.drop('money', axis=1, inplace=True)

    # 先用 VWAP 过滤缩小候选池，确保回退时也不会选到 VWAP 不达标的股票
    _vwap_pass_codes = vwap_above_ratio[(vwap_above_ratio >= VWAP_ABOVE_MIN) & (vwap_above_ratio <= VWAP_ABOVE_MAX)].index.tolist()
    pre_picks = pre_picks[pre_picks.index.isin(_vwap_pass_codes)]
    if len(pre_picks) == 0:
        result['skipped_reason'] = 'VWAP过滤后无候选（全部不在%.0f%%~%.0f%%区间）' % (VWAP_ABOVE_MIN * 100, VWAP_ABOVE_MAX * 100)
        return result

    final_table = min_final.join(
        pre_picks[['pct_chg', 'circulating_market_cap', 'circulating_cap', 'money']], how='inner')
    final_table['turnover'] = (vol_intra / (final_table['circulating_cap'] * 10000)) * 100
    final_table['vwap_above_pct'] = final_table.index.map(vwap_above_ratio).fillna(0)

    mask_pro = (
        (final_table['close'] >= final_table['vwap']) &
        (final_table['upper_shadow'] <= UPPER_SHADOW_MAX) &
        (final_table['vol_ratio'] >= VOL_RATIO_MIN) & (final_table['vol_ratio'] <= VOL_RATIO_MAX) &
        (final_table['turnover'] >= TURNOVER_MIN) & (final_table['turnover'] <= TURNOVER_MAX)
    )
    filtered_df = final_table[mask_pro]
    _fallback = False
    _filter_reasons = {}
    if len(filtered_df) == 0:
        if not FALLBACK_RANGE or len(FALLBACK_RANGE) < 2:
            result['skipped_reason'] = '精筛后无标的'
            return result
        _fb_sorted = final_table.sort_values(by='money', ascending=False)
        _fb_start, _fb_end = FALLBACK_RANGE[0], FALLBACK_RANGE[1]
        _fb_total = len(_fb_sorted)
        if _fb_start >= _fb_total:
            result['skipped_reason'] = '回退区间[%d,%d]超出候选数%d' % (_fb_start, _fb_end, _fb_total)
            return result
        _fb_end = min(_fb_end, _fb_total - 1)
        filtered_df = _fb_sorted.iloc[_fb_start:_fb_end + 1]
        
        # 记录每只回退股被精筛过滤掉的原因
        _filter_reasons = {}
        for _c in filtered_df.index.tolist():
            _reasons = []
            _row = final_table.loc[_c]
            if _row['close'] < _row['vwap']:
                _reasons.append('VWAP')
            if _row['upper_shadow'] > UPPER_SHADOW_MAX:
                _reasons.append('上影%.1f%%' % _row['upper_shadow'])
            if _row['vol_ratio'] < VOL_RATIO_MIN:
                _reasons.append('量比%.2f<%.1f' % (_row['vol_ratio'], VOL_RATIO_MIN))
            if _row['vol_ratio'] > VOL_RATIO_MAX:
                _reasons.append('量比%.2f>%.1f' % (_row['vol_ratio'], VOL_RATIO_MAX))
            if _row['turnover'] < TURNOVER_MIN:
                _reasons.append('换手%.1f%%<%.0f%%' % (_row['turnover'], TURNOVER_MIN))
            if _row['turnover'] > TURNOVER_MAX:
                _reasons.append('换手%.1f%%>%.0f%%' % (_row['turnover'], TURNOVER_MAX))
            _filter_reasons[_c] = ','.join(_reasons) if _reasons else ''
        
        if GLOBAL_RISK_WARN:
            _gr_codes = set()
            _m = target_date[5:7]
            for _c in filtered_df.index.tolist():
                _sector = sector_map.get(_c, '')
                _sector_l1 = sector_l1_map.get(_c, '')
                _sector_l2 = sector_l2_map.get(_c, '')
                _name = stocks_info.loc[_c, 'display_name'] if _c in stocks_info.index else ''
                for _kw in RISK_SECTORS:
                    if _kw in _sector or _kw in _sector_l1 or _kw in _sector_l2 or _kw in _name:
                        _gr_codes.add(_c)
                        break
                for _kw in RISK_STOCKS:
                    if _kw in _name or _kw in _c:
                        _gr_codes.add(_c)
                        break
            if _gr_codes:
                _safe_codes = [c for c in filtered_df.index.tolist() if c not in _gr_codes]
                if not _safe_codes:
                    result['skipped_reason'] = '回退后全局风险过滤：所有标的均有风险信号'
                    return result
                filtered_df = filtered_df.loc[_safe_codes]
        _fallback = True

    if hasattr(filtered_df, 'sort_values'):
        _sorted = filtered_df.sort_values(by='money', ascending=False)
    else:
        _sorted = filtered_df.sort(columns='money', ascending=False)
    picks = _sorted.head(TOP_N).copy(deep=True)
    if _fallback:
        result['skipped_reason'] = '精筛无标的->回退区间[%d,%d]' % (FALLBACK_RANGE[0], FALLBACK_RANGE[1])

    # --- 顶部风险扫描 + 过滤 ---
    _pick_risk_tags = {}  # {code: [tag strings]}
    if FILTER_TOP_RISK:
        _orig_pick_codes = picks.index.tolist()

        # 1. MA20 / MA60 乖离率
        try:
            _df_ma_raw = get_price(_orig_pick_codes, count=60, end_date=target_date,
                                   frequency='daily', fields=['close'], panel=False)
            if _df_ma_raw is not None and len(_df_ma_raw) > 0:
                _df_ma = _df_ma_raw.reset_index()
                if 'index' in _df_ma.columns:
                    _df_ma.drop('index', axis=1, inplace=True)
                _df_ma = _df_ma.loc[:, ~_df_ma.columns.duplicated()]
                _ma_grp = _df_ma.groupby('code')['close']
                _ma20_s = _ma_grp.rolling(20, min_periods=20).mean().groupby('code').last()
                _ma60_s = _ma_grp.rolling(60, min_periods=60).mean().groupby('code').last()
                for _c in _orig_pick_codes:
                    if _c in _ma20_s.index:
                        _close = float(picks.loc[_c, 'close'])
                        _ma20 = float(_ma20_s.loc[_c])
                        _dev20 = (_close - _ma20) / _ma20 * 100
                        if _dev20 > WARN_DEVIATION_MA20:
                            _pick_risk_tags.setdefault(_c, []).append(
                                "dev_MA20_+%.1f%%" % _dev20)
                    if _c in _ma60_s.index:
                        _close = float(picks.loc[_c, 'close'])
                        _ma60 = float(_ma60_s.loc[_c])
                        _dev60 = (_close - _ma60) / _ma60 * 100
                        if _dev60 > WARN_DEVIATION_MA60:
                            _pick_risk_tags.setdefault(_c, []).append(
                                "dev_MA60_+%.1f%%" % _dev60)
        except Exception as _e:
            print("[W] 乖离率扫描异常: %s" % str(_e))

        # 2. 量比 + 换手率过热
        for _c in _orig_pick_codes:
            try:
                _vr = float(picks.loc[_c, 'vol_ratio'])
                _to = float(picks.loc[_c, 'turnover'])
                if _vr >= WARN_OVERHEAT_VOL and _to >= WARN_OVERHEAT_TURN:
                    _pick_risk_tags.setdefault(_c, []).append(
                        "overheat_v%.1f_t%.1f%%" % (_vr, _to))
            except Exception:
                pass

        # 3. 跳空高开 + 横盘出货
        try:
            _df_first = df_min_flat.groupby('code').first()
            for _c in _orig_pick_codes:
                if _c not in _df_first.index or _c not in t_day_basic.index:
                    continue
                _open_val = float(_df_first.loc[_c, 'open']) if 'open' in _df_first.columns else float(_df_first.loc[_c, 'close'])
                _pre_c = float(t_day_basic.loc[_c, 'pre_close'])
                if _pre_c <= 0:
                    continue
                _gap_pct = (_open_val - _pre_c) / _pre_c * 100
                if _gap_pct >= WARN_GAP_OPEN_PCT:
                    _c_data = df_min_flat[df_min_flat['code'] == _c]
                    _day_high = float(_c_data['high'].max())
                    _day_low = float(_c_data['low'].min())
                    _range_pct = (_day_high - _day_low) / _open_val * 100
                    if _range_pct < WARN_GAP_FLAT_RANGE:
                        _pick_risk_tags.setdefault(_c, []).append(
                            "gap_flat_+%.1f%%_%.1f%%" % (_gap_pct, _range_pct))
        except Exception as _e:
            print("[W] 盘中形态检查异常: %s" % str(_e))

        # 4. 板块内跟风排名
        try:
            _sector_df = pre_picks[pre_picks['sector'] != ''][['sector', 'pct_chg']].copy()
            _sector_df['rank_pct'] = _sector_df.groupby('sector')['pct_chg'].rank(pct=True, ascending=False)
            for _c in _orig_pick_codes:
                if _c in _sector_df.index:
                    _rp = float(_sector_df.loc[_c, 'rank_pct'])
                    if _rp >= WARN_SECTOR_RANK_PCT:
                        _pick_risk_tags.setdefault(_c, []).append(
                            "follow_rank_%.0f%%" % (_rp * 100))
        except Exception as _e:
            print("[W] 板块排名检查异常: %s" % str(_e))

        # 5. 量价背离：近5日涨但量能萎缩
        if df_hist is not None and len(df_hist) > 0:
            try:
                for _c in _orig_pick_codes:
                    _c_hist = df_hist[df_hist['code'] == _c].sort_values('time')
                    if len(_c_hist) < 5:
                        continue
                    _last5 = _c_hist.tail(5)
                    _last10 = _c_hist.tail(10) if len(_c_hist) >= 10 else _c_hist
                    _p_first = float(_last5['close'].iloc[0])
                    if _p_first <= 0:
                        continue
                    _pct_5d = (float(_last5['close'].iloc[-1]) - _p_first) / _p_first * 100
                    _avg_vol_5d = float(_last5['volume'].mean())
                    _avg_vol_10d = float(_last10['volume'].mean())
                    if _pct_5d > 0 and _avg_vol_5d < _avg_vol_10d:
                        _pick_risk_tags.setdefault(_c, []).append(
                            "diverg_+%.1f%%_v5<v10" % _pct_5d)
            except Exception as _e:
                print("[W] 量价背离检查异常: %s" % str(_e))

        # --- 过滤/提示 ---
        _safe_codes = [c for c in _orig_pick_codes if c not in _pick_risk_tags]
        _filtered_out = len(_orig_pick_codes) - len(_safe_codes)
        if _filtered_out > 0:
            if len(_orig_pick_codes) == 1:
                if FILTER_TOP_RISK_SINGLE:
                    print("    [顶部风险] 仅1只标的，触发风险: %s(%s)，执行过滤" % (
                        _orig_pick_codes[0], ','.join(_pick_risk_tags.get(_orig_pick_codes[0], []))))
                    if len(_safe_codes) == 0:
                        result['skipped_reason'] = '顶部风险过滤：唯一标的触发风险信号'
                        return result
                    picks = picks.loc[_safe_codes]
                else:
                    print("    [顶部风险] 仅1只标的，不做过滤，风险提示: %s(%s)" % (
                        _orig_pick_codes[0], ','.join(_pick_risk_tags.get(_orig_pick_codes[0], []))))
                    _filtered_out = 0
            else:
                print("    [顶部风险] 过滤 %d 只: %s" % (
                    _filtered_out,
                    ', '.join('%s(%s)' % (c, ','.join(_pick_risk_tags[c])) for c in _pick_risk_tags)))
                if len(_safe_codes) == 0:
                    result['skipped_reason'] = '顶部风险过滤：所有标的均有风险信号'
                    return result
                picks = picks.loc[_safe_codes]
        result['top_risk_filtered'] = _filtered_out

    # --- 全局风险过滤 ---
    if GLOBAL_RISK_WARN:
        _gr_codes = set()
        _m = target_date[5:7]
        _cur_codes = picks.index.tolist()
        if _m in RISK_MONTHS:
            print("    [全局风险] 当前为历史高风险月份(%s月)，全量回测显示该月胜率偏低" % _m)
        for _c in _cur_codes:
            _sector = sector_map.get(_c, '')
            _sector_l1 = sector_l1_map.get(_c, '')
            _sector_l2 = sector_l2_map.get(_c, '')
            _name = stocks_info.loc[_c, 'display_name'] if _c in stocks_info.index else ''
            for _kw in RISK_SECTORS:
                if _kw in _sector or _kw in _sector_l1 or _kw in _sector_l2 or _kw in _name:
                    _gr_codes.add(_c)
                    break
            for _kw in RISK_STOCKS:
                if _kw in _name or _kw in _c:
                    _gr_codes.add(_c)
                    break
        if _gr_codes:
            _safe = [c for c in _cur_codes if c not in _gr_codes]
            print("    [全局风险] 过滤 %d 只: %s" % (len(_gr_codes), ','.join(sorted(_gr_codes))))
            if not _safe:
                result['skipped_reason'] = '全局风险过滤：所有标的均有风险信号'
                return result
            picks = picks.loc[_safe]

    # --- 延迟卖出逻辑 ---
    pick_codes = picks.index.tolist()
    _today_str = _dt.date.today().strftime('%Y-%m-%d')
    
    # 每只股票的买入价
    buy_prices = {code: float(picks.loc[code, 'close']) for code in pick_codes}
    
    # 每只股票的卖出记录：{code: {'sell_date': '', 'sell_price': 0, 'sold': False}}
    sell_records = {code: {'sell_date': '', 'sell_price': 0.0, 'sold': False} for code in pick_codes}
    
    _pending = False
    
    import pandas as _pd
    
    # 逐日检查卖出条件
    for day_idx, sell_date in enumerate(sell_days):
        if sell_date >= _today_str:
            _pending = True
            continue
        
        # 检查是否还有未卖出的股票
        unsold_codes = [code for code in pick_codes if not sell_records[code]['sold']]
        if not unsold_codes:
            break
        
        is_final_day = (day_idx == len(sell_days) - 1)
        is_first_day = (day_idx == 0)
        
        # 获取当日分钟线数据
        _sell_end = sell_date + ' ' + SELL_TIME
        try:
            df_sm = get_price(unsold_codes, start_date=sell_date + ' 09:30:00',
                              end_date=_sell_end, frequency='1m', fields=['close'], panel=False)
        except Exception:
            df_sm = None
        
        if df_sm is None or len(df_sm) == 0:
            continue
        
        df_smf = df_sm.reset_index()
        if 'index' in df_smf.columns:
            df_smf.drop('index', axis=1, inplace=True)
        df_smf = df_smf.loc[:, ~df_smf.columns.duplicated()]
        df_smf = df_smf.sort_values(['code', 'time'])
        
        # 对每只未卖出的股票检查卖出条件
        for code in unsold_codes:
            bp = buy_prices[code]
            _sub = df_smf[df_smf['code'] == code]
            if len(_sub) == 0:
                continue
            
            # 获取卖出时间点的价格
            if SELL_TIME == '15:00:00':
                _sp = float(_sub.iloc[-1]['close'])
            elif SELL_TIME == '09:30:00':
                _sp = float(_sub.iloc[0]['close'])
            else:
                # 找到最接近SELL_TIME的分钟
                _target_time = sell_date + ' ' + SELL_TIME
                _sp = float(_sub.iloc[-1]['close'])
                for _i in range(len(_sub)):
                    _row = _sub.iloc[_i]
                    _t = str(_row['time'])[:19]
                    if _t >= _target_time:
                        _sp = float(_row['close'])
                        break
            
            # 检查止损
            _stop_triggered = False
            for _i in range(len(_sub)):
                _row = _sub.iloc[_i]
                _c = float(_row['close'])
                _pct = (_c - bp) / bp * 100
                if _pct <= STOP_LOSS_PCT:
                    _sp = _c
                    _stop_triggered = True
                    break
            
            # 判断是否卖出
            _should_sell = False
            if _stop_triggered:
                # 触发止损，立即卖出
                _should_sell = True
            elif is_first_day and is_final_day:
                # 只有一天（DELAY_SELL_DAYS=0）：强制卖出（与原来逻辑一致）
                _should_sell = True
            elif is_first_day:
                # T+1日：盈利则卖出
                if _sp > bp:
                    _should_sell = True
            elif is_final_day:
                # 最后一天：强制卖出
                _should_sell = True
            else:
                # 中间日：回本则卖出
                if _sp >= bp:
                    _should_sell = True
            
            if _should_sell:
                sell_records[code] = {
                    'sell_date': sell_date,
                    'sell_price': _sp,
                    'sold': True
                }
    
    # 处理未卖出的股票（pending状态）
    for code in pick_codes:
        if not sell_records[code]['sold']:
            if _pending:
                # 未来日期，按买入价占位
                sell_records[code] = {
                    'sell_date': sell_days[-1] if sell_days else '',
                    'sell_price': buy_prices[code],
                    'sold': True
                }
            else:
                # 历史日期但未卖出（数据缺失），按买入价
                sell_records[code] = {
                    'sell_date': sell_days[-1] if sell_days else '',
                    'sell_price': buy_prices[code],
                    'sold': True
                }

    # 每日本金均分：每只分配 DAILY_CAPITAL / N，按手（100股）向下取整
    # 回退选股时按 FALLBACK_POSITION_RATIO 比例减仓
    _n_picks = len(pick_codes)
    _capital = DAILY_CAPITAL * FALLBACK_POSITION_RATIO if _fallback else DAILY_CAPITAL
    _cap_per = _capital / _n_picks if _n_picks else 0.0
    details = []
    total_buy = 0.0
    total_sell = 0.0
    for code in pick_codes:
        bp = float(picks.loc[code, 'close'])
        sp = sell_records[code]['sell_price']
        sell_date = sell_records[code]['sell_date']
        # 按手取整：1手=100股
        _lots = int(_cap_per / (bp * 100)) if bp > 0 else 0
        shares = _lots * 100
        pnl = (sp - bp) * shares
        total_buy += bp * shares
        total_sell += sp * shares
        def _g(col):
            try:
                return float(picks.loc[code, col])
            except Exception:
                return float('nan')
        details.append({
            'code': code,
            'name': stocks_info.loc[code, 'display_name'] if code in stocks_info.index else '',
            'sector': sector_map.get(code, ''),
            'sector_l2': sector_l2_map.get(code, ''),
            'sector_l1': sector_l1_map.get(code, ''),
            'buy': round(bp, 3),
            'sell': round(sp, 3),
            'sell_date': sell_date,
            'shares': shares,
            'pnl': round(pnl, 2),
            'pnl_pct': round((sp - bp) / bp * 100, 2) if bp > 0 else 0.0,
            'pct_chg': round(_g('pct_chg'), 2),
            'mkt_cap': round(_g('circulating_market_cap'), 2),
            'vol_ratio': round(_g('vol_ratio'), 2),
            'upper_shadow': round(_g('upper_shadow'), 2),
            'turnover': round(_g('turnover'), 2),
            'vwap_above_pct': round(_g('vwap_above_pct'), 2),
            'fallback': _fallback,
            'l1_fallback': _l1_fallback,
            'filter_reason': _filter_reasons.get(code, ''),
        })

    result['picks_count'] = len(pick_codes)
    result['total_buy'] = total_buy
    result['total_sell'] = total_sell
    result['total_pnl'] = total_sell - total_buy
    result['pnl_pct'] = (total_sell - total_buy) / total_buy * 100 if total_buy else 0.0
    result['details'] = details
    result['pending'] = _pending
    if _pending:
        result['skipped_reason'] = (result.get('skipped_reason') or '') + '次日数据未产生(待揭晓,按0盈亏)'

    _minute_rows = []
    try:
        for _mc in pick_codes:
            _mc_df = df_min_flat[df_min_flat['code'] == _mc][['time', 'open', 'close', 'high', 'low', 'avg', 'volume']].copy()
            _mc_df['code'] = _mc
            _mc_df['name'] = stocks_info.loc[_mc, 'display_name'] if _mc in stocks_info.index else ''
            _mc_df['buy_price'] = buy_prices[_mc]
            _mc_df['pnl_pct_vs_buy'] = (_mc_df['close'] - buy_prices[_mc]) / buy_prices[_mc] * 100
            _minute_rows.append(_mc_df)
        if _minute_rows:
            import pandas as _pd3
            result['minute_data'] = _pd3.concat(_minute_rows, ignore_index=True)
        else:
            result['minute_data'] = None
    except Exception:
        result['minute_data'] = None

    return result


# ============================================================
# 月度主流程
# ============================================================
def run_month(backtest_str):
    # 解析输入：月份(YYYY-MM) 或 具体日期(YYYY-MM-DD)
    _parts = backtest_str.split('-')
    _is_date_mode = len(_parts) == 3 and len(_parts[2]) == 2
    _year, _mo = _parts[0], _parts[1]
    _y = int(_year); _m = int(_mo)
    if _is_date_mode:
        _start = backtest_str
        _end = backtest_str
        _day = int(_parts[2])
        if _m == 12:
            _next_1 = datetime(_y + 1, 1, 1)
        else:
            _next_1 = datetime(_y, _m + 1, 1)
    else:
        _start = '%04d-%02d-01' % (_y, _m)
        if _m == 12:
            _next_1 = datetime(_y + 1, 1, 1)
        else:
            _next_1 = datetime(_y, _m + 1, 1)
        _end = (_next_1 - timedelta(days=1)).strftime('%Y-%m-%d')
    _end_buf = (_next_1 + timedelta(days=15)).strftime('%Y-%m-%d')

    all_trade_days = list(get_trade_days(start_date=_start, end_date=_end_buf))
    if len(all_trade_days) == 0:
        print("[ERR] %s 无交易日" % backtest_str)
        return
    month_days = [d for d in all_trade_days if _start <= str(d) <= _end]
    if len(month_days) == 0:
        print("[ERR] %s 无交易日" % backtest_str)
        return

    print("=" * 100)
    if _is_date_mode:
        print("【单日回测】 日期: %s" % backtest_str)
    else:
        print("【月度回测】 月份: %s  月内交易日: %d 个  (%s ~ %s)" % (
            backtest_str, len(month_days), str(month_days[0]), str(month_days[-1])))
    print("=" * 100)

    # 缓存股票列表（月内不变，省开销）
    stocks_info_cache = get_all_securities(['stock'])

    all_results = []
    for _idx, _d in enumerate(month_days):
        d_str = str(_d)
        # 跳过未来日期
        _today_str = _dt.date.today().strftime('%Y-%m-%d')
        if d_str > _today_str:
            print("[%s] 跳过：未来日期" % d_str)
            continue
        # 找下一交易日（可能跨月）
        try:
            _pos = all_trade_days.index(_d)
        except ValueError:
            continue
        if _pos + 1 >= len(all_trade_days):
            print("[%s] 跳过：无下一交易日可卖出" % d_str)
            continue
        
        # 构建交易日列表（T+1 到 T+N）
        _sell_days = []
        for _i in range(1, DELAY_SELL_DAYS + 2):  # +2 因为 range 不包含上界
            if _pos + _i < len(all_trade_days):
                _sell_days.append(str(all_trade_days[_pos + _i]))
        
        if not _sell_days:
            print("[%s] 跳过：无交易日可卖出" % d_str)
            continue
        
        next_d_str = _sell_days[0]
        sell_days_str = ','.join(_sell_days) if len(_sell_days) > 1 else _sell_days[0]

        print("\n[%d/%d] 选股日: %s  卖出日: %s" % (_idx + 1, len(month_days), d_str, sell_days_str))
        try:
            r = screen_one_day(d_str, _sell_days, stocks_info_cache=stocks_info_cache)
        except Exception as e:
            import traceback
            print("    [ERR] %s" % str(e))
            traceback.print_exc()
            r = {'date': d_str, 'next_day': next_d_str, 'picks_count': 0,
                 'total_buy': 0, 'total_sell': 0, 'total_pnl': 0, 'pnl_pct': 0,
                 'details': [], 'skipped_reason': 'exception: ' + str(e)[:50]}

        if r['picks_count'] == 0:
            print("    -> 无交易 (%s)" % r.get('skipped_reason', ''))
        else:
            _tag = ' [待揭晓]' if r.get('pending') else ''
            print("    -> 选中 %d 只%s | 买入 %.0f | 卖出 %.0f | 盈亏 %+.2f (%+.2f%%)" % (
                r['picks_count'], _tag, r['total_buy'], r['total_sell'], r['total_pnl'], r['pnl_pct']))
            _scl1 = r.get('sector_chg_l1', {})
            _scl2 = r.get('sector_chg_l2', {})
            _scl3 = r.get('sector_chg_l3', {})
            print("       %-12s %-8s %6s %7s %7s %5s %6s %6s %6s %7s %-10s %-10s %-10s %-10s %8s" % (
                "代码", "名称", "市值(亿)", "买入价", "涨幅%", "量比", "换手%", "上影%", "VWAP%", "卖出价", "卖出日期", "一级行业", "二级行业", "三级行业", "盈亏"))
            for d in r['details']:
                _fb_tag = ' [回退]' if d.get('fallback') else ''
                _filter_tag = '(%s)' % d.get('filter_reason', '') if d.get('filter_reason') else ''
                _l1_fb_tag = ' [回退一级行业]' if d.get('l1_fallback') else ''
                _sell_date = d.get('sell_date', '')
                _s1 = d.get('sector_l1', '')
                _s2 = d.get('sector_l2', '')
                _s3 = d.get('sector', '')
                _l1v = _scl1.get(_s1, 0)
                _l2v = _scl2.get(_s2, 0)
                _l3v = _scl3.get(_s3, 0)
                _l1f = '%s%+6.2f%%' % (_pad(_s1, 6), _l1v)
                _l2f = '%s%+6.2f%%' % (_pad(_s2, 8), _l2v)
                _l3f = '%s%+6.2f%%' % (_s3, _l3v)
                print("       %-12s %-8s %6.1f %7.2f %+6.2f%% %5.1f %5.1f%% %5.2f %5.0f%% %7.2f %s  %s  %s  %s %+8.2f%s%s%s" % (
                    d['code'], d['name'], d['mkt_cap'], d['buy'],
                    d['pct_chg'], d['vol_ratio'], d['turnover'], d['upper_shadow'],
                    d.get('vwap_above_pct', 0) * 100,
                    d['sell'], _sell_date,
                    _l1f, _l2f, _l3f, d['pnl'], _fb_tag, _filter_tag, _l1_fb_tag))
            _check_global_risks(r['details'], r['date'])
        # 大盘 + 情绪比值信息（每天都打印）
        if 'sentiment_ratio' in r:
            print("    [大盘] 上证%+.2f%% 指数%.2f | 涨%d/%d 成交%.2f万亿 | 情绪比值 %.2f (需 >=%.2f) %s" % (
                r.get('sh_change', 0.0), r.get('sh_index', 0.0),
                r.get('sh_rise_count', 0), r.get('sh_total_stock', 0),
                r.get('sh_total_money', 0) / 1e12,
                r.get('sentiment_ratio', 0.0), r.get('sentiment_need', 0.0),
                (u'[风险]' + r.get('sentiment_warning', '')) if r.get('sentiment_warning') else u'[通过]'))
            # 当日一级行业涨跌
            _top_l1 = r.get('top_l1_sectors', [])[:5]
            if _top_l1:
                _l1_parts = ["%s %+.2f%%" % (n, v) for n, v in _top_l1]
                print("    [L1行业] " + " | ".join(_l1_parts))
        all_results.append(r)

    # --- 月度汇总 ---
    print("\n" + "=" * 100)
    print("【汇总】 %s" % backtest_str)
    print("=" * 100)

    traded = [r for r in all_results if r['picks_count'] > 0]
    skipped = [r for r in all_results if r['picks_count'] == 0]

    _total_buy  = sum(r['total_buy']  for r in traded)
    _total_sell = sum(r['total_sell'] for r in traded)
    _total_pnl  = _total_sell - _total_buy
    _total_pct  = (_total_pnl / DAILY_CAPITAL * 100) if DAILY_CAPITAL else 0.0
    _win_days   = sum(1 for r in traded if r['total_pnl'] > 0)
    _lose_days  = sum(1 for r in traded if r['total_pnl'] < 0)

    print("交易日数: %d | 有交易: %d | 跳过: %d" % (
        len(all_results), len(traded), len(skipped)))
    print("盈利日: %d | 亏损日: %d | 胜率: %.1f%%" % (
        _win_days, _lose_days,
        (_win_days / len(traded) * 100) if traded else 0.0))
    print("合计买入: %.2f | 合计卖出: %.2f" % (_total_buy, _total_sell))
    print("本金: %.2f | 合计盈亏: %+.2f  (%+.2f%%)" % (DAILY_CAPITAL, _total_pnl, _total_pct))

    _fb_details = [d for r in traded for d in r.get('details', []) if d.get('fallback')]
    if _fb_details:
        _fb_buy  = sum(d.get('buy', 0) * d.get('shares', 0) for d in _fb_details)
        _fb_sell = sum(d.get('sell', 0) * d.get('shares', 0) for d in _fb_details)
        _fb_pnl  = _fb_sell - _fb_buy
        _fb_pct  = (_fb_pnl / _fb_buy * 100) if _fb_buy else 0.0
        _fb_win  = sum(1 for d in _fb_details if d.get('pnl', 0) > 0)
        _fb_lose = sum(1 for d in _fb_details if d.get('pnl', 0) < 0)
        print("回退股:   %d只 | 盈利: %d | 亏损: %d | 胜率: %.1f%%" % (
            len(_fb_details), _fb_win, _fb_lose,
            (_fb_win / len(_fb_details) * 100) if _fb_details else 0.0))
        print("回退股盈亏: %+.2f  (%+.2f%%)" % (_fb_pnl, _fb_pct))

    _all_details = [d for r in traded for d in r.get('details', [])]
    if _all_details:
        _vwap_groups = [
            ('VWAP>=98%%', [d for d in _all_details if d.get('vwap_above_pct', 0) >= 0.98]),
            ('VWAP 95-98%%', [d for d in _all_details if 0.95 <= d.get('vwap_above_pct', 0) < 0.98]),
            ('VWAP<95%%', [d for d in _all_details if d.get('vwap_above_pct', 0) < 0.95]),
        ]
        print("\n【VWAP区间统计】")
        for _label, _group in _vwap_groups:
            if _group:
                _g_pnl = sum(d.get('pnl', 0) for d in _group)
                _g_buy = sum(d.get('buy', 0) * d.get('shares', 0) for d in _group)
                _g_pct = (_g_pnl / _g_buy * 100) if _g_buy else 0.0
                _g_win = sum(1 for d in _group if d.get('pnl', 0) > 0)
                _g_lose = sum(1 for d in _group if d.get('pnl', 0) < 0)
                print("  %-12s: %3d只 | 盈利: %d | 亏损: %d | 胜率: %5.1f%% | 盈亏: %+.2f  (%+.2f%%)" % (
                    _label, len(_group), _g_win, _g_lose,
                    (_g_win / len(_group) * 100) if _group else 0.0,
                    _g_pnl, _g_pct))
            else:
                print("  %-12s:   0只" % _label)

    # 每日明细表
    print("\n【每日盈亏明细】")
    print("-" * 130)
    print("%-12s  %-12s  %-12s  %6s  %12s  %12s  %12s  %8s  %10s  %8s" % (
        "选股日", "卖出日", "大盘涨跌", "只数", "买入", "卖出", "盈亏", "盈亏%", "成交额(亿)", "情绪比值"))
    print("-" * 130)
    for r in all_results:
        if r['picks_count'] > 0:
            _tag = ' [待揭晓]' if r.get('pending') else ''
            _sh_chg_str = "%+.2f%%" % r.get('sh_change', 0.0)
            _money_yi = r.get('sh_total_money', 0) / 1e8
            _sent_val = r.get('sentiment_ratio', 0.0)
            # 计算实际卖出日期范围
            _sell_dates = [d.get('sell_date', '') for d in r.get('details', []) if d.get('sell_date')]
            if _sell_dates:
                _sell_dates = sorted(set(_sell_dates))
                if len(_sell_dates) == 1:
                    _sell_day_str = _sell_dates[0]
                else:
                    _sell_day_str = '%s~%s' % (_sell_dates[0], _sell_dates[-1])
            else:
                _sell_day_str = r['next_day']
            print("%-12s  %-12s  %-12s  %6d  %12.2f  %12.2f  %+12.2f  %+7.2f%%%s  %10.0f  %8.2f" % (
                r['date'], _sell_day_str, _sh_chg_str, r['picks_count'],
                r['total_buy'], r['total_sell'], r['total_pnl'], r['pnl_pct'], _tag,
                _money_yi, _sent_val))
        else:
            _sh_chg_str = "%+.2f%%" % r.get('sh_change', 0.0)
            _money_yi = r.get('sh_total_money', 0) / 1e8
            _sent_val = r.get('sentiment_ratio', 0.0)
            print("%-12s  %-12s  %-12s  %6s  %-s" % (
                r['date'], r['next_day'], _sh_chg_str, '-',
                '跳过: ' + r.get('skipped_reason', '')))
    print("-" * 130)
    print("=" * 100)

    # --- CSV 导出 ---
    if EXPORT_CSV:
        try:
            _export_csv(backtest_str, all_results)
        except Exception as _e:
            import traceback
            print("[WARN] CSV 导出失败: %s" % str(_e))
            traceback.print_exc()


def _export_csv(backtest_str, all_results):
    """导出逐笔交易明细 CSV（中文表头）。
       研究环境中写入后，左侧文件树可见并支持下载。
    """
    import csv, os, codecs
    _prefix = (CSV_DIR.rstrip('/\\') + '/') if CSV_DIR else ''
    trades_path = '%sbacktest_%s_trades.csv' % (_prefix, backtest_str)

    headers = ['回测区间', '大盘指数', '当日上证涨跌幅', '大盘上涨', '大盘下跌', '大盘总股票数', '大盘总成交额', '大盘总成交量',
               '情绪比值', '情绪比值需求', '情绪风险提示',
               '代码', '名称', '市值(亿)', '价格', '涨幅%', '量比', '换手%', '上影线%', 'VWAP上方占比',
               '一级行业', '一级涨幅%', '二级行业', '二级涨幅%', '三级行业', '三级涨幅%',
               '买入日期', '实际卖出日期', '盈亏', '盈亏%', '是否回退选股', '精筛过滤原因', '是否回退一级行业']

    # 写 UTF-8 BOM，便于 Excel 直接打开不乱码
    with open(trades_path, 'wb') as f:
        f.write(codecs.BOM_UTF8)
    with open(trades_path, 'a') as f:
        w = csv.writer(f)
        w.writerow([h.encode('utf-8') if isinstance(h, unicode) else h for h in headers]
                   if str is bytes else headers)
        _scl1 = {}
        _scl2 = {}
        _scl3 = {}
        for r in all_results:
            if not r.get('details'):
                continue
            _sh = r.get('sh_change', '')
            _scl1 = r.get('sector_chg_l1', {})
            _scl2 = r.get('sector_chg_l2', {})
            _scl3 = r.get('sector_chg_l3', {})
            for d in r['details']:
                _s1 = d.get('sector_l1', '')
                _s2 = d.get('sector_l2', '')
                _s3 = d.get('sector', '')
                row = [
                    backtest_str,
                    r.get('sh_index', ''),
                    _sh,
                    r.get('sh_rise_count', ''),
                    r.get('sh_fall_count', ''),
                    r.get('sh_total_stock', ''),
                    r.get('sh_total_money', ''),
                    r.get('sh_total_volume', ''),
                    r.get('sentiment_ratio', ''),
                    r.get('sentiment_need', ''),
                    r.get('sentiment_warning', ''),
                    d.get('code', ''),
                    d.get('name', ''),
                    d.get('mkt_cap', ''),
                    d.get('buy', ''),
                    d.get('pct_chg', ''),
                    d.get('vol_ratio', ''),
                    d.get('turnover', ''),
                    d.get('upper_shadow', ''),
                    d.get('vwap_above_pct', ''),
                    _s1, _scl1.get(_s1, ''),
                    _s2, _scl2.get(_s2, ''),
                    _s3, _scl3.get(_s3, ''),
                    r.get('date', ''),
                    d.get('sell_date', ''),
                    d.get('pnl', ''),
                    d.get('pnl_pct', ''),
                    '是' if d.get('fallback') else '否',
                    d.get('filter_reason', ''),
                    '是' if d.get('l1_fallback') else '否',
                ]
                # py2 兼容：str 写出
                if str is bytes:
                    row = [x.encode('utf-8') if isinstance(x, unicode) else x for x in row]
                w.writerow(row)

    try:
        _sz = os.path.getsize(trades_path)
    except Exception:
        _sz = -1
    print("\n[CSV] 已导出：%s  (%d bytes)" % (trades_path, _sz))
    print("       聚宽研究环境：左侧【文件】面板可见，右键即可下载。")

    _minute_path = '%sbacktest_%s_minute.csv' % (_prefix, backtest_str)
    _min_headers = ['选股日', '代码', '名称', '买入价', '时间', '开盘', '收盘', '最高', '最低',
                    '均价', '成交量', 'vs买入价盈亏%']
    _min_count = 0
    with open(_minute_path, 'wb') as f:
        f.write(codecs.BOM_UTF8)
    with open(_minute_path, 'a') as f:
        w = csv.writer(f)
        w.writerow([h.encode('utf-8') if isinstance(h, unicode) else h for h in _min_headers]
                   if str is bytes else _min_headers)
        for r in all_results:
            _md = r.get('minute_data')
            if _md is None or len(_md) == 0:
                continue
            _date_str = r['date']
            for _, _row in _md.iterrows():
                _out_row = [
                    _date_str,
                    _row.get('code', ''),
                    _row.get('name', ''),
                    round(_row.get('buy_price', 0), 3),
                    str(_row.get('time', ''))[:19],
                    round(float(_row.get('open', 0)), 3),
                    round(float(_row.get('close', 0)), 3),
                    round(float(_row.get('high', 0)), 3),
                    round(float(_row.get('low', 0)), 3),
                    round(float(_row.get('avg', 0)), 3),
                    int(_row.get('volume', 0)),
                    round(float(_row.get('pnl_pct_vs_buy', 0)), 2),
                ]
                if str is bytes:
                    _out_row = [x.encode('utf-8') if isinstance(x, unicode) else x for x in _out_row]
                w.writerow(_out_row)
                _min_count += 1
    try:
        _msz = os.path.getsize(_minute_path)
    except Exception:
        _msz = -1
    print("[CSV] 已导出分时线：%s  (%d rows, %d bytes)" % (_minute_path, _min_count, _msz))


# ============================================================
# 入口
# ============================================================
run_month(TARGET_DATE)

