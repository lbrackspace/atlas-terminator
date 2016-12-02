create table entry(
    id int not null auto_increment,
    entry_id varchar(45),
    tenant_id int,
    event_time datetime,
    event varchar(16),
    entrybody text,
    is_our_account tinyint(1),
    needs_push tinyint(1),
    created_time datetime,
    finished_time datetime,
    num_attemps int not null,
    primary key(id)
)engine=InnoDB charset=utf8;

alter table entry add unique index entry_id_idx(entry_id);
alter table entry add index tenant_idx(tenant_id);
alter table entry add index event_time_idx(event_time);
alter table entry add index needs_push_idx(needs_push);


create table log(
    id int not null auto_increment,
    tenant_id int,
    created_time datetime,
    log text,
    primary key(id)
)engine=InnoDB charset=utf8;

alter table log add index tenant_id_idx(tenant_id);
alter table log add index created_time_idx(created_time);

