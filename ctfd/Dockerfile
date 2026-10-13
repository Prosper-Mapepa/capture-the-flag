FROM ctfd/ctfd:3.7.7

USER root
COPY plugins/squirrel_join /opt/CTFd/CTFd/plugins/squirrel_join
COPY railway-entrypoint.sh /railway-entrypoint.sh
RUN chown -R 1001:1001 /opt/CTFd/CTFd/plugins/squirrel_join \
 && chmod +x /railway-entrypoint.sh

ENTRYPOINT ["/railway-entrypoint.sh"]
