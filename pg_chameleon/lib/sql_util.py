import re

class sql_token:
	"""
	Class sql_token. Tokenise the sql statements captured by the mysql replication.
	Each statement is converted in a python dictionary being used by pg_engine.
	"""
	def __init__(self):
		self.tokenised=[]
		self.query_list=[]
		
		#re for column definitions
		self.m_columns=re.compile(r'\((.*)\)', re.IGNORECASE)
		self.m_inner=re.compile(r'\((.*)\)', re.IGNORECASE)
		#[^,]+[,\s\d\)]+[\w\s]+[,]
		#[^,](\([\d\s,]+\))?
		#transform comma in pipe for dimensions like (30,20) so is safe to split using the comma search
		#((\(\s?\d+\s?),(\s?\d+\s?\)))
		#r.sub(r"\2|\3",sql)
		#re for keys and indices
		self.m_pkeys=re.compile(r',\s*PRIMARY\s*KEY\s*\((.*?)\)\s*', re.IGNORECASE)
		self.m_ukeys=re.compile(r',\s*UNIQUE\s*KEY\s*`?\w*`?\s*\((.*?)\)\s*', re.IGNORECASE)
		self.m_keys=re.compile(r',\s*(?:UNIQUE)?\s*(?:KEY|INDEX)\s*`?\w*`?\s*\((?:.*?)\)\s*', re.IGNORECASE)
		self.m_idx=re.compile(r',\s*(?:KEY|INDEX)\s*`?\w*`?\s*\((.*?)\)\s*', re.IGNORECASE)
		self.m_fkeys=re.compile(r',\s*CONSTRAINT\s*`?\w*`?\s*FOREIGN\s*KEY(?:.*?)(?:ON\s*(?:DELETE|UPDATE)\s*(?:RESTRICT|CASCADE)\s*)+', re.IGNORECASE)
		
		#re for fields
		self.m_field=re.compile(r'(?:`)?(\w*)(?:`)?\s*(?:`)?(\w*\s*(?:precision|varying)?)(?:`)?\s*((\(\s*\d*\s*\)|\(\s*\d*\s*,\s*\d*\s*\))?)', re.IGNORECASE)
		self.m_dbl_dgt=re.compile(r'((\(\s?\d+\s?),(\s?\d+\s?\)))',re.IGNORECASE)
		self.m_dimension=re.compile(r'\((.*)\)', re.IGNORECASE)
		self.m_pars=re.compile(r'(\((:?.*?)\))', re.IGNORECASE)
		#self.m_enum=re.compile(r'\s*enum\s*\((.*?)\)', re.IGNORECASE|re.DOTALL)
		self.m_fields=re.compile(r'(.*?),', re.IGNORECASE)
		#re for column constraint and auto incremental
		self.m_nulls=re.compile(r'(NOT)?\s*(NULL)', re.IGNORECASE)
		self.m_autoinc=re.compile(r'(AUTO_INCREMENT)', re.IGNORECASE)
		
		#re for query type
		self.m_create_table=re.compile(r'(CREATE\s*TABLE)\s*(?:IF\s*NOT\s*EXISTS)?\s*(?:`)?(\w*)(?:`)?', re.IGNORECASE)
		self.m_drop_table=re.compile(r'(DROP\s*TABLE)\s*(?:IF\s*EXISTS)?\s*(?:`)?(\w*)(?:`)?', re.IGNORECASE)
		
	def reset_lists(self):
		self.tokenised=[]
		self.query_list=[]
		
	def parse_column(self, col_def):
		colmatch=self.m_field.search(col_def)
		dimmatch=self.m_dimension.search(col_def)
		#enmatch=self.m_enum.search(col_def)
		#print col_def
		
		col_dic={}
		if colmatch:
			col_dic["column_name"]=colmatch.group(1).strip("`").strip()
			col_dic["data_type"]=colmatch.group(2).lower().strip()
			col_dic["is_nullable"]="YES"
			if dimmatch:
				col_dic["enum_list"]=dimmatch.group(1).strip().replace('|', ',')
				col_dic["character_maximum_length"]=dimmatch.group(1).strip().replace('|', ',')
				col_dic["numeric_precision"]=dimmatch.group(1).strip().replace('|', ',')
			nullcons=self.m_nulls.search(col_def)
			autoinc=self.m_autoinc.search(col_def)
			if nullcons:
				if nullcons.group(0)=="NOT NULL":
					col_dic["is_nullable"]="NO"
				else:
					col_dic["is_nullable"]="YES"
			if autoinc:
				col_dic["extra"]="auto_increment"
			else :
				col_dic["extra"]=""
		return col_dic
	
	def build_key_dic(self, inner_stat, table_name):
		key_dic={}
		idx_list=[]
		idx_counter=0
		inner_stat=inner_stat.strip()
		#print inner_stat

		pkey=self.m_pkeys.findall(inner_stat)
		ukey=self.m_ukeys.findall(inner_stat)
		idx=self.m_idx.findall(inner_stat)
		if pkey:
			key_dic["index_name"]='PRIMARY'
			key_dic["index_columns"]=pkey[0]
			key_dic["non_unique"]=0
			idx_list.append(dict(key_dic.items()))
			key_dic={}
		if ukey:
			for cols in ukey:
				key_dic["index_name"]='ukidx_'+table_name[0:20]+'_'+str(idx_counter)
				key_dic["index_columns"]=cols
				key_dic["non_unique"]=0
				idx_list.append(dict(key_dic.items()))
				key_dic={}
				idx_counter+=1
		if idx:
			for cols in idx:
				key_dic["index_name"]='idx_'+table_name[0:20]+'_'+str(idx_counter)
				key_dic["index_columns"]=cols
				key_dic["non_unique"]=1
				idx_list.append(dict(key_dic.items()))
				key_dic={}
				idx_counter+=1
		return idx_list
		
	def build_column_dic(self, inner_stat):
		column_list=self.m_fields.findall(inner_stat)
		#print inner_stat
		cols_parse=[]
		for col_def in column_list:
			col_def=col_def.strip()
			col_dic=self.parse_column(col_def)
			if col_dic:
				cols_parse.append(col_dic)
		return cols_parse
		
	
	def parse_create_table(self, sql_create, table_name):
		m_inner=self.m_inner.search(sql_create)
		inner_stat=m_inner.group(1).strip()
		table_dic={}
		column_list=self.m_pkeys.sub( '', inner_stat)
		column_list=self.m_keys.sub( '', column_list)
		column_list=self.m_idx.sub( '', column_list)
		column_list=self.m_fkeys.sub( '', column_list)
		table_dic["indices"]=self.build_key_dic(inner_stat, table_name)
		#column_list=self.m_dbl_dgt.sub(r"\2|\3",column_list)
		mpars=self.m_pars.findall(column_list)
		for match in mpars:
			new_group=str(match[0]).replace(',', '|')
			column_list=column_list.replace(match[0], new_group)
		column_list=column_list+","
		#print column_list
		table_dic["columns"]=self.build_column_dic(column_list)
		#for item in table_dic["columns"]:
		#	print item
		return table_dic	
		
	def parse_sql(self, sql_string):
		"""
			Splits the sql string in statements using the conventional end of statement marker ;
			A regular expression greps the words and parentesis and a split converts them in
			a list. Each list of words is then stored in the list token_list.
			
			:param sql_string: The sql string with the sql statements.
		"""
		sql_string=re.sub(r'\s+default(.*?),', ' ', sql_string, re.IGNORECASE)
		statements=sql_string.split(';')
		for statement in statements:
			stat_dic={}
			stat_cleanup=re.sub(r'/\*.*?\*/', '', statement, re.DOTALL)
			stat_cleanup=re.sub(r'--.*?\n', '', stat_cleanup)
			stat_cleanup=re.sub(r'[\b)\b]', ' ) ', stat_cleanup)
			stat_cleanup=re.sub(r'[\b(\b]', ' ( ', stat_cleanup)
			stat_cleanup=re.sub(r'[\b,\b]', ', ', stat_cleanup)
			stat_cleanup=re.sub(r'\n*', '', stat_cleanup)
			stat_cleanup=re.sub("\([\w*\s*]\)", " ",  stat_cleanup)
			stat_cleanup=stat_cleanup.strip()
			mcreate_table=self.m_create_table.match(stat_cleanup)
			mdrop_table=self.m_drop_table.match(stat_cleanup)
			#print stat_cleanup
			if mcreate_table:
				command=' '.join(mcreate_table.group(1).split()).upper().strip()
				stat_dic["command"]=command
				stat_dic["name"]=mcreate_table.group(2)
				create_parsed=self.parse_create_table(stat_cleanup, stat_dic["name"])
				stat_dic["columns"]=create_parsed["columns"]
				stat_dic["indices"]=create_parsed["indices"]
				
			elif mdrop_table:
				command=' '.join(mdrop_table.group(1).split()).upper().strip()
				stat_dic["command"]=command
				stat_dic["name"]=mdrop_table.group(2)
			self.tokenised.append(stat_dic)
