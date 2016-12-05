create table terminator(
    id int not null auto_increment,
    uuid varchar(45),
    tenant_id int,
    event_time datetime,
    event varchar(16),
    entrybody text,
    is_our_account tinyint(1),
    needs_push tinyint(1),
    created_time datetime,
    finished_time datetime,
    primary key(id)
)engine=InnoDB charset=utf8;

alter table terminator add unique index uuid_idx(uuid);
alter table terminator add index tenant_idx(tenant_id);
alter table terminator add index event_time_idx(event_time);
alter table terminator add index needs_push_idx(needs_push);


create table log(
    id int not null auto_increment,
    tenant_id int,
    created_time datetime,
    log text,
    primary key(id)
)engine=InnoDB charset=utf8;

alter table log add index tenant_id_idx(tenant_id);