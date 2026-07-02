# getFirmCommercialGeneral — Response Field Reference

Response `data` object sections. Arrays unless noted.

## commercialRegInfo (基础信息) — object

| Field | Description |
|---|---|
| firmName | 企业名称 |
| uscCode | 统一社会信用代码 |
| regNo | 注册号 |
| orgCode | 组织机构代码 |
| legalRep | 法定代表人 |
| estDate | 成立日期 |
| openDate | 营业开始日期 |
| closeDate | 营业结束日期 |
| apprDate | 核准日期 |
| cancelDate | 注销日期 |
| revDate | 撤销日期 |
| revReason | 撤销原因 |
| regCap | 注册资本 |
| recCap | 实缴资本 |
| regCapCur | 货币单位 |
| opeStatus | 经营状态 |
| opeStatusCode | 经营状态码 |
| firmType | 企业类型 |
| firmClassOne | 企业一级分类 |
| firmClassTwo | 企业二级分类 |
| indEconCode | 行业代码 |
| indEconName | 行业名称 |
| opeScope | 经营范围 |
| regAddress | 注册地址 |
| regAgency | 登记机关 |
| areaCode | 地区代码 |
| firmNameUsed | 曾用名 (array) |

## shareholderInfo (股东信息) — array

| Field | Description |
|---|---|
| shaName | 股东名称 |
| shaType | 股东类型 (自然人/法人) |
| holdRatio | 持股比例 |
| cumulativeAmt | 累计出资额 |
| accRealCap | 实缴出资 |
| identifyType | 证件类型 |
| identifyNo | 证件号 |
| subItems | 认缴明细 (array: subCap, subCapDate, subCapMode) |
| realItems | 实缴明细 (array: realCap, realCapDate, realCapMode) |

## keymanInfo (主要人员) — array

| Field | Description |
|---|---|
| admPrimName | 姓名 |
| admPrimPosition | 职务 |

## firmBranchInfo (分支机构) — array

| Field | Description |
|---|---|
| brName | 分支机构名称 |
| brStatus | 状态 (存续/注销/吊销) |
| brPrincipal | 负责人 |
| brEstDate | 成立日期 |
| brRegAgency | 登记机关 |
| brRegCap | 注册资本 |
| brUscCode | 统一社会信用代码 |

## investmentInfo (对外投资) — array

| Field | Description |
|---|---|
| invName | 被投资企业名称 |
| invRatio | 投资比例 |
| invAmt | 投资金额 |
| invRegStatus | 被投资企业经营状态 |
| invRegCap | 被投资企业注册资本 |
| invUscCode | 统一社会信用代码 |
| invLegalRep | 被投资企业法定代表人 |
| invEstDate | 投资日期 |
| financeDate | 财务日期 |

## equityPledgeInfo (股权出质) — array

| Field | Description |
|---|---|
| pledgeNo | 出质编号 |
| pledgeStatus | 状态 (有效/无效) |
| pledgorName | 出质人 |
| pledgorIdNo | 出质人证件号 |
| pledgorType | 出质人类型 |
| pledgeeName | 质权人 |
| pledgeeIdNo | 质权人证件号 |
| pledgeAmt | 出质金额 |
| pledgeAmtCur | 币种 |
| pledgeAmtUnit | 金额单位 |
| objectCompany | 标的企业 |
| pledgeRegDate | 登记日期 |
| disabled | 是否失效 |
| changeItems | 变更明细 |
| remark | 备注 |

## mortgageInfo (动产抵押) — array

| Field | Description |
|---|---|
| mortRegNo | 抵押编号 |
| mortStatus | 状态 |
| mortRegDate | 登记日期 |
| mortRegAgency | 登记机关 |
| debitAmount | 债权金额 |
| debitCurrency | 币种 |
| debitType | 债权类型 |
| debitPeriod | 债权期限 |
| debitScope | 债权范围 |
| guaranteeAmt | 担保金额 |
| guaranteeScope | 担保范围 |
| guaranteeType | 担保类型 |
| guarantees | 抵押物 (array) |
| mortgagees | 抵押权人 (array) |
| closeDate | 注销日期 |
| closeReason | 注销原因 |
| period | 期间 |
| remarks | 备注 |

## frozenInfo (股权冻结) — array

| Field | Description |
|---|---|
| court | 法院 |
| noticeNo | 通知书文号 |
| enforceName | 被执行人 |
| equityAmt | 股权数额 |
| frozenShareStatus | 冻结状态 |
| type | 类型 |
| freezeDetail | 冻结明细 (object) |
| pcfreezeDetail | 续行冻结明细 (object) |
| continueFreezeDetails | 续行冻结 (array) |
| unfreezeDetail | 解冻 (array) |
| loseEfficacy | 失效信息 (object) |

## businessAlter (变更记录) — array

| Field | Description |
|---|---|
| altItem | 变更事项 |
| altType | 变更类型 |
| altBefore | 变更前 |
| altAfter | 变更后 |
| altDate | 变更日期 |

## admLicenInfo (行政许可) — array

| Field | Description |
|---|---|
| licenseContent | 许可内容 |
| licenseAgency | 许可机关 |
| licenseStartDate | 开始日期 |
| licenseEndDate | 结束日期 |
| licenseStatus | 状态 |
| licenseStatusCode | 状态码 |
| licenseNo | 许可编号 |
| licenseFileName | 文件名 |
| source | 来源 |
| disabled | 是否当前公示 |

## Other sections

| Section | Type | Description |
|---|---|---|
| doubleRandomCheck | array | 双随机抽查 (checkAgency, checkDate, checkResult, checkType) |
| spotCheck | array | 抽查检查 |
| commercialAdmPenal | array | 行政处罚 (penalAgency, penalReason, penalBasis, penalDeciDate) |
| abnorOpeInfo | array | 经营异常 (abnorOpeInReason, abnorOpeOutReason) |
| simpleCancelInfo | array | 简易注销 |
| clearInfo | array | 清算信息 (liquidationMember, liquidationPrincipal) |
| seriousBreachTrust | array | 严重违法失信 (includedReason, includedDate, removeDate) |

## Response Codes

| Code | Description |
|---|---|
| 0000 | 查询成功 |
| 0001 | 查询成功,但无数据 |
| 1001 | 业务异常 |
| 1002 | 传入参数为空或格式错误 |
| 1020 | 系统查询有异常,请联系技术人员 |
| 200 | OK |
| 9998 | 搜索词太宽泛 |
| 9999 | 系统异常 |
