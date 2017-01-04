drop table if exists users;
drop table if exists vacations;
create table users (
	id integer primary key autoincrement,
	google_id text not null,
	rights integer not null
);
create table vacations (
	id integer primary key autoincrement,
	user_id integer not null,
	start_date text not null,
	end_date text not null,
	approved integer not null
)
